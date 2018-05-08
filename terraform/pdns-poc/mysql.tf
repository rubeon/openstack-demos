resource "aws_instance" "mysql_master" {
    ami = "${data.aws_ami.mysql_ami.id}"
    instance_type = "${var.instance_types["mysql_master"]}"
    key_name = "${var.key}"
    subnet_id = "${aws_subnet.public_subnet.id}"
    
    tags {
        Name = "${var.environment_name}-mysql_master"
        ansible_role = "db_master"
        environment = "${var.environment_name}"
    }
    
    vpc_security_group_ids = [
        "${aws_security_group.mysql.id}"
    ]
}

resource "aws_instance" "mysql_slave" {
    ami = "${data.aws_ami.mysql_ami.id}"
    instance_type = "${var.instance_types["mysql_master"]}"
    key_name = "${var.key}"
    subnet_id = "${aws_subnet.public_subnet.id}"
    
    tags {
        Name = "${var.environment_name}-db_slave"
        ansible_role = "db_slave"
        environment = "${var.environment_name}"
    }
    
    vpc_security_group_ids = [
        "${aws_security_group.mysql.id}"
    ]
}

resource "aws_security_group" "mysql" {
    vpc_id = "${aws_vpc.vpc.id}"
    name = "mysql-security-group"
    
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
        from_port = 3306
        to_port = 3306
        protocol = "tcp"
        cidr_blocks = [
            "10.0.0.0/8"
        ]
    }
    ingress {
        from_port = 3306
        to_port = 3306
        protocol = "tcp"
        cidr_blocks = [
            "10.0.0.0/8"
        ]
        
    }
    
}

