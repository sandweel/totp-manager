resource "aws_ebs_volume" "main" {
  availability_zone = data.aws_availability_zones.available.names[0]
  size              = 10
}
