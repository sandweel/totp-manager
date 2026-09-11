variable "aws_region" {
  description = "AWS region"
}

variable "brand" {
  description = "Project name"
}

variable "environment" {
  description = "Project environment"
}

variable "instance_type" {
  description = "EC2 instance type"
}

variable "instance_ami" {
  description = "EC2 AMI id"
}

variable "ssh_key_name" {
  description = "Name of the existing SSH key pair in AWS"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
}

variable "subnet_cidr" {
  description = "CIDR block for the public subnet"
  type        = string
}

variable "domain_name" {
  description = "Full domain name (e.g., app.example.com)"
  type        = string
}

variable "ssm_totp_mailgun_key" {
  description = "Mailgun API key"
  type        = string
}
variable "ssm_totp_mailgun_domain" {
  description = "Maingun sender domain"
  type        = string
}

variable "repository_name" {
  description = "HTTPS/SSH repository name"
  type        = string
}

variable "ebs_size" {
  description = "EBS size for docker volumes (/mnt)"
  type        = string
}
