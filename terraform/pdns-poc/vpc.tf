# there's a VPC for the POC
resource "aws_vpc" "vpc" {
    cidr_block = "10.100.0.0/16"
    enable_dns_support = true
    enable_dns_hostnames = true
    
    tags {
        Name = "${var.environment_name}-vpc"
    }
}

# A front-facing public subnet
resource "aws_subnet" "public_subnet" {
    vpc_id = "${aws_vpc.vpc.id}"
    cidr_block = "10.100.1.0/24"
    map_public_ip_on_launch = true
    
    tags {
        Name = "${var.environment_name}-public"
    }
}

# A backend private subnet
resource "aws_subnet" "private_subnet" {
    vpc_id = "${aws_vpc.vpc.id}"
    cidr_block = "10.100.2.0/24"
    map_public_ip_on_launch = false
    
    tags {
        Name = "${var.environment_name}-private"
    }
}

# An internet gateway
resource "aws_internet_gateway" "gw" {
    vpc_id = "${aws_vpc.vpc.id}"
    tags {
        Name = "${var.environment_name}-gw"
    }

}

# A public IP
resource "aws_eip" "nat" {
    vpc = true
    depends_on = [
        "aws_internet_gateway.gw"
    ]    
}

resource "aws_route" "internet_access" {
  route_table_id         = "${aws_vpc.vpc.main_route_table_id}"
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = "${aws_internet_gateway.gw.id}"
}


# A security group for the NATted instances
resource "aws_security_group" "nat" {
    name = "vpc_nat"
    description = "Allows traffic to pass from the public subnet to the internet"
    vpc_id = "${aws_vpc.vpc.id}"
    
    ingress {
        from_port = 80
        to_port = 80
        protocol = "tcp"
        cidr_blocks = [
            "${aws_subnet.private_subnet.cidr_block}"
        ]
    }
    ingress {
        from_port = 443
        to_port = 443
        protocol = "tcp"
        cidr_blocks = [
            "${aws_subnet.private_subnet.cidr_block}"
        ]
    }
    ingress {
        from_port = 22
        to_port = 22
        protocol = "tcp"
        cidr_blocks = [
            "0.0.0.0/0"
        ]
    }
    
    ingress {
        from_port = -1
        to_port = -1
        protocol = "icmp"
        cidr_blocks = [
            "0.0.0.0/0"
        ]
    }
    
    egress {
        from_port = 80
        to_port = 80
        protocol = "tcp"
        cidr_blocks = [
            "0.0.0.0/0"
        ]
    }
    egress {
        from_port = 443
        to_port = 443
        protocol = "tcp"
        cidr_blocks = [
            "0.0.0.0/0"
        ]
    }
    egress {
        from_port = 22
        to_port = 22
        protocol = "tcp"
        cidr_blocks = [
            "0.0.0.0/0"
        ]
    }
    egress {
        from_port = -1
        to_port = -1
        protocol = "icmp"
        cidr_blocks = [
            "0.0.0.0/0"
        ]
    }
}

resource "aws_nat_gateway" "natgw" {
  allocation_id = "${aws_eip.nat.id}"
  subnet_id     = "${aws_subnet.private_subnet.id}"
}
