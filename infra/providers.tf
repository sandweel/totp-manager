provider "aws" {
  region = var.aws_region


  default_tags {
    tags = {
      environment   = var.environment
      brand         = var.brand
      managed_by    = "terraform"
    }
  }
}

terraform {
  backend "s3" {
    bucket         = "totp-tf-state"
    key            = "prod/terraform.tfstate"
    region         = "eu-central-1"
    encrypt        = true
  }
}