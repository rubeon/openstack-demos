terraform {
    backend "local" {
        path = "terraform.tstate"
    }
}
# setup the AWS provider
# credentials will be pulled from environment variables
provider "aws" {
    region = "eu-west-1"
    shared_credentials_file = "${pathexpand("~/.aws/config")}"
    
}

data "aws_ami" "dns_master_ami" {
    most_recent = true
    owners = ["410186602215"]
    name_regex = "CentOS Linux 7.*"
    filter {
      name = "virtualization-type"
      values = ["hvm"]
    }
    
}

data "aws_ami" "client_ami" {
    most_recent = true
    owners = ["410186602215"]
    name_regex = "CentOS Linux 7.*"
    filter {
        name = "virtualization-type"
        values = ["hvm"]
    }
}

data "aws_ami" "mysql_ami" {
    most_recent = true
    owners = ["410186602215"]
    name_regex = "CentOS Linux 7.*"
    filter {
        name = "virtualization-type"
        values = ["hvm"]
    }
}


variable "environment_name" {
    default = "powerdns-poc-terraform-phase2"
    description = "The name of this environment"
}

variable "instance_types" {
    description = "Map of instance types for resources"
    type = "map"
    
    default = {
        dns_master = "m3.large"
        client = "m3.medium"
        mysql_master = "m3.large"
        mysql_slave = "m3.large"
    }
}

variable "key" {
    default = "ehw-aws-powerdns"
    description = "Key to use for this deployment"
}