#!/usr/bin/python

from pprint import pprint
import yaml

cslist = open('cloud_server_list.csv').readlines()
footprints = {}
network_prefix = "RC-CLOUD-"

# using a global image mapping for this:
images = {}

images['winbase']="85533cc6-6776-460c-a5f5-b9b0c7ed915d"
images['iscsi']="d8df5db8-2c82-484d-99a9-f3517721dd74"
images['iscsi1']="d8df5db8-2c82-484d-99a9-f3517721dd74"
images['winbase1']="85533cc6-6776-460c-a5f5-b9b0c7ed915d"
images['iscsi2']="d8df5db8-2c82-484d-99a9-f3517721dd74"
images['iscsi3']="d8df5db8-2c82-484d-99a9-f3517721dd74"

for cs in cslist:
    environment, vlan, hostname, description, ip, flavor, volume, volume_size, image = cs.split(',')
    # create a server record
    if description == 'description' or description=='':
        # this is the header or footer
        continue
    
    if environment not in footprints.keys():
        footprints[environment]={}
    footprints[environment]['footprint']=environment    

    if 'servers' not in footprints[environment].keys():
        print "Adding", environment
        footprints[environment]['servers']={}
    footprints[environment]['servers']['images']=images
    vlan = network_prefix + vlan
    
    s = {}
    # set the ip addresses
    s['ip-addresses']={}
    s['ip-addresses'][vlan]=ip

    s['hostname']=hostname.strip()
    s['description']=description.strip()
    s['flavor']=flavor.strip()
    s['volume']=volume.strip()
    s['volume_size']=int(volume_size.strip())
    s['vlan']=vlan.strip()
    s['image']=image.strip()
    footprints[environment]['servers'][hostname] = s
    


for fp in footprints.keys():
    yamlfile = open("%s.yaml" % fp, 'w')
    yamlfile.write(yaml.dump(footprints[fp]))
    yamlfile.close()
