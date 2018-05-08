resource "aws_instance" "dns-master" {
    ami = "${data.aws_ami.dns_master_ami.id}"
    instance_type = "m3.medium"
    key_name = "${var.key}"
    subnet_id = "${aws_subnet.public_subnet.id}"
    
    tags {
        Name = "${var.environment_name}-dns-master"
        ansible_role = "dns_master"
        environment = "${var.environment_name}"
    }
    
    /*security_groups = [
        "${aws_security_group.dns-master.id}"
    ]*/
    vpc_security_group_ids = [
        "${aws_security_group.dns-master.id}"
    ]
}

resource "aws_security_group" "dns-master" {
    vpc_id = "${aws_vpc.vpc.id}"
    name = "dns-master-security-group"
    
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
    ingress {
        from_port = 53
        to_port = 53
        protocol = "tcp"
        cidr_blocks = [
            "10.0.0.0/8"
        ]
    }
    ingress {
        from_port = 53
        to_port = 53
        protocol = "udp"
        cidr_blocks = [
            "10.0.0.0/8"
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
    
}

