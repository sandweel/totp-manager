resource "random_id" "encryption_key" {
  byte_length = 32
}

resource "random_password" "secret_key" {
  length  = 64
  special = true
}

resource "aws_ssm_parameter" "encryption_key" {
  name        = "totp-encryption-key"
  description = "Encryption key for Fernet"
  type        = "SecureString"
  value       = random_id.encryption_key.b64_std
}

resource "aws_ssm_parameter" "secret_key" {
  name        = "totp-secret-key"
  description = "Secret key for JWT signing"
  type        = "SecureString"
  value       = random_password.secret_key.result
}