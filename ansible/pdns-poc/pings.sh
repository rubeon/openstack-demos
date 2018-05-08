#!/bin/bash
#shift
ssh -t -l vagrant -i files/vagrant_key 172.16.1.203 $*
ssh -t -l vagrant -i files/vagrant_key 172.16.1.136 $*
ssh -t -l vagrant -i files/vagrant_key 172.16.1.138 $*
ssh -t -l vagrant -i files/vagrant_key 172.16.1.204 $*
ssh -t -l vagrant -i files/vagrant_key 172.16.1.134 $*
ssh -t -l vagrant -i files/vagrant_key 172.16.2.3 $*
ssh -t -l vagrant -i files/vagrant_key 172.16.1.135 $*

