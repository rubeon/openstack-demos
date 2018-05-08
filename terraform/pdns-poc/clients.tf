resource "aws_instance" "client1" {
    ami = "${data.aws_ami.client_ami.id}"
    instance_type = "${var.instance_types["client"]}"
    key_name = "${var.key}"
    subnet_id = "${aws_subnet.private_subnet.id}"
    
    tags {
        Name = "${var.environment_name}-client1"
        ansible_role = "client"
        environment = "${var.environment_name}"
    }
    
    vpc_security_group_ids = [
        "${aws_security_group.client.id}"
    ]
}

resource "aws_security_group" "client" {
    vpc_id = "${aws_vpc.vpc.id}"
    name = "client-security-group"
    
    # allow all ssh
    ingress {
        from_port = 22
        to_port = 22
        protocol = "tcp"
        cidr_blocks = [
            "0.0.0.0/0"
        ]
    }
    # allow incoming DNS from local networks
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
        from_port = 53
        to_port = 53
        protocol = "tcp"
        cidr_blocks = [
            "0.0.0.0/0"
        ]
    }
    egress {
        from_port = 53
        to_port = 53
        protocol = "udp"
        cidr_blocks = [
            "10.0.0.0/8"
        ]
    }
    
}

