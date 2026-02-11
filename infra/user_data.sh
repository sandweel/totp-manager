#!/bin/bash

VOLUME_ID="${volume_id}"
RECORD_NAME="${domain_name}"
REPOSITORY_NAME="${repository_name}"

apt update
apt install -y jq python3-pip ca-certificates curl

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "$${UBUNTU_CODENAME:-$$VERSION_CODENAME}")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

pip3 install awscli --break-system-packages

TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/instance-id)
REGION=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/placement/region)

aws ec2 attach-volume --volume-id $VOLUME_ID --instance-id $INSTANCE_ID --device /dev/sdf --region $REGION

while [ ! -b /dev/nvme1n1 ]; do sleep 1; done

if ! blkid /dev/nvme1n1; then
  mkfs.ext4 /dev/nvme1n1
fi

mkdir -p /mnt/app /app
for dir in {mysql,logs,alembic_versions,data}
do
     if [ ! -d $dir ];then
          mkdir $dir
     fi
done

mount /dev/nvme1n1 /mnt/app

git clone $REPOSITORY_NAME /app
cd /app

cat <<EOF > .env
PORT=80
FRONTEND_URL=https://${domain_name}
COOKIE_SECURE=true
ACCESS_TOKEN_EXPIRE_MINUTES=5
REFRESH_TOKEN_EXPIRE_DAYS=30
GUNICORN_WORKERS=1

DATABASE_URL=mysql+asyncmy://${db_user}:${db_user_pass}@db:3306/${db_name}

ENCRYPTION_KEY=$(aws ssm get-parameter --name "${ssm_encryption_key_name}" --with-decryption --region ${aws_region} --query "Parameter.Value" --output text)
SECRET_KEY=$(aws ssm get-parameter --name "${ssm_secret_key_name}" --with-decryption --region ${aws_region} --query "Parameter.Value" --output text)
MAILGUN_API_KEY=$(aws ssm get-parameter --name "${ssm_totp_mailgun_key}" --with-decryption --region ${aws_region} --query "Parameter.Value" --output text)
MAILGUN_DOMAIN=$(aws ssm get-parameter --name "${ssm_totp_mailgun_domain}" --with-decryption --region ${aws_region} --query "Parameter.Value" --output text)
EOF

cat <<EOF > .env_db
MYSQL_DATABASE=${db_name}
MYSQL_USER=${db_user}
MYSQL_PASSWORD=${db_user_pass}
EOF

cat <<'EOF' > docker-compose-ec2.yml
services:
  db:
    image: mariadb:10.11
    container_name: totp-manager-db
    restart: unless-stopped
    env_file:
      - .env_db
    environment:
      MYSQL_ALLOW_EMPTY_PASSWORD: true
    volumes:
      - /mnt/app/mysql:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  app:
    build: .
    container_name: totp-manager-app
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    env_file:
      - .env
    ports:
      - "$${PORT:-8000}:8000"
    volumes:
      - /mnt/app/logs:/app/logs
      - /mnt/app/data:/app/data
      - /mnt/app/alembic_versions:/app/alembic/versions
EOF

docker compose -f docker-compose-ec2.yml build --no-cache
docker compose -f docker-compose-ec2.yml up -d
