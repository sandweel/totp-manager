resource "random_string" "db_name" {
  length  = 8
  special = false
  upper   = false
}

resource "random_string" "db_user" {
  length  = 8
  special = false
  upper   = false
}

resource "random_password" "db_pass" {
  length           = 16
  special          = true
  override_special = "#$^&*"
}

resource "aws_instance" "main" {
  ami           = var.instance_ami
  instance_type = var.instance_type
  user_data_replace_on_change = true

  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.main.id]
  key_name                    = var.ssh_key_name
  associate_public_ip_address = true

  iam_instance_profile = aws_iam_instance_profile.instance_profile.name

  user_data = templatefile("${path.module}/user_data.sh", {
    volume_id                   = aws_ebs_volume.main.id
    ssm_encryption_key_name     = aws_ssm_parameter.encryption_key.name
    ssm_secret_key_name         = aws_ssm_parameter.secret_key.name
    db_name                     = random_string.db_name.result
    db_user                     = random_string.db_user.result
    db_user_pass                = random_password.db_pass.result
    aws_region                  = var.aws_region
    domain_name                 = var.domain_name
    repository_name             = var.repository_name
    ssm_totp_mailgun_key        = var.ssm_totp_mailgun_key
    ssm_totp_mailgun_domain     = var.ssm_totp_mailgun_domain
  })
}
