#!/usr/bin/env python
# This script sniffs out the IP addresses for 
# deployed machines in VSphere.  This is mainly 
# a workaround for the lousy Ansible inventory support
# for VCenter servers.

import os
import ConfigParser
import pyVmomi
import ssl
import yaml
from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect

# disable ssl certificate checks
ssl._create_default_https_context = ssl._create_unverified_context


def connect(config):
  # takes a dictionary of the following form to connect
  # config = {
  #   'vcenter_server': 'MyUser,'
  #   'vsphere_username': 'MyUser',
  #   'vsphere_password': 'MyPass'
  #
  # }
  user = config.get('default', 'vsphere_username')
  pwd =  config.get('default', 'vsphere_password')
  host = config.get('default', 'vcenter_server')
  
  return SmartConnect(
    host = host,
    pwd = pwd,
    user = user
  )

def get_obj(content, vimtype, name):
    """
    Return an object by name, if name is None the
    first found object is returned
    """
    obj = None
    container = content.viewManager.CreateContainerView(
        content.rootFolder, vimtype, True)
    for c in container.view:
        if name:
            if c.name == name:
                obj = c
                break
        else:
            obj = c
            break

    return obj

def get_machine_list(content, rg_name):
  """docstring for get_machine_list"""

  rg = get_obj(content, [vim.ResourcePool], rg_name)
  if rg:
    return rg.vm
  else:
    return []
  
  
def main():
  config = ConfigParser.ConfigParser()
  with open(os.path.expanduser("~/.vmwarerc")) as fd:
    config.readfp(fd)
  print "Hi o/"
  conn = connect(config)
  content = conn.RetrieveContent()
  siteconfig = yaml.load(open('vars/siteconfig.yaml'))
  
  # get the resource group
  for site_name in ['zone1','zone2']:
    for application_environment in ['stg1', 'stg2']:
      tmpl = "%-50s %25s"
      rg_name = "%s-pdnspoc-resource-pool-%s" % (site_name, application_environment)
      print "Resource Pool:", rg_name
      for machine in get_machine_list(content, rg_name):
        # for nic in my_vm.guest.net:
        addresses = []
        for nic in machine.guest.net:
          addresses.extend([i.ipAddress for i in nic.ipConfig.ipAddress])
        machine_name = machine.name
        for address in addresses:
          print tmpl % (machine_name, address)
          machine_name = ""
        print ""
  

if __name__ == '__main__':
  main()