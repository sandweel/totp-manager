output "instance_eip" {
  value       = aws_eip.main.public_ip
  description = "The static Elastic IP address"
}

output "aws_ec2_start_command" {
  description = "AWS CLI command to start the instance"
  value       = "aws ec2 start-instances --instance-ids ${aws_instance.main.id} --region ${var.aws_region}"
}

output "aws_ec2_stop_command" {
  description = "AWS CLI command to stop the instance"
  value       = "aws ec2 stop-instances --instance-ids ${aws_instance.main.id} --region ${var.aws_region}"
}

output "ebs_volume_id" {
  value = aws_ebs_volume.main.id
}
