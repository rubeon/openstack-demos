#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
next action: save / load / create networks for footprints

* Load
1. load footprint config
2. check if network exists
3. if it does, then create network object with that UUID

* save
1. write json object containing network <=> uuid mapping

* create
1. load footprint config
2. check if network exists
3. if it doesn't, create the network object
4. then create the network itself
5. save it


"""


import os
import sys
import logging
# termios, fnctl, struct are used to determine terminal width in progress table
import termios
import fcntl
import struct
# keyring used to hold pyrax auth
import keyring
# configuration files use yaml
import yaml
# import argparse to handle the command-line parsing
import argparse
# time is used while polling / monitor
import time
# json is used to serialize the state of footprintss
import json
# getpass used for generating initial configuration
import getpass
# pprint does some debug printing 
import pprint
# prettytables used for showing config et.al
import prettytable
# used for catching Nova API errors
import novaclient.exceptions
# use time and datetime for profiling
import time
import datetime

# define some defaults
start_time = time.time()
RACKCONNECT = True

logging.basicConfig(filename="rspec.log", level=logging.DEBUG, 
    format='%(asctime)s [%(levelname)s] %(message)s')

import pyrax
cn = None
cs = None
cf = None

## FIXME
# remove this when ready to start testing with the customer account
if os.environ.get("OS_USERNAME") == "customer-cloud":
    print "WARNING: Currently configured to use account 'customer-cloud'"
    raw_input("enter to continue, ^C to break")

# this script needs to:
# - clone Gold Standard Dev Environments into 'footprints'
# - spin up existing 'footprints' 
# - spin down 'footprints'
# - track different environment 'footprints'

def notify(msg, timestamp=True):
    """
    wrapper for printing / logging notifications
    takes a string
    """
    if timestamp:
        note = "[%8.2f] %s\n" % (time.time(), msg)
    else:
        note = "%s\n" % (msg)
    sys.stdout.write(note)
    sys.stdout.flush()

class Environment(object):
    """
    an environment is a group of footprints
    
    when instantiated, it will attempt to load its metadata
    from the cloudfiles collection "rspec-master".
    
    This will include a list of pointers to 'known' footprints.
    """        
    container_name = "footprint-master"
    # footprints will be a list of dictionaries
    # this will be a {'fpname':'container_name'} pairing
    footprints = {}
    container = None
    
    def __init__(self):
        """
        init function; sets up containers
        """
        # try to load the container
        # cf will be global... 
        # self.cf = pyrax.cloudfiles
        logging.debug("Opening cloudfiles container '%s'" % self.container_name)
        notify("Reading environment configuration")
        
        # check if our container exists; if not create it
        all_containers = cf.list_containers()
        
        if self.container_name in all_containers:
            logging.debug("Container exists, opening")
            mycontainer = cf.get_container(self.container_name)
        else:
            logging.warn("Container doesn't exist, creating...")
            mycontainer = cf.create_container(self.container_name)
            
        self.container = mycontainer
        
        if not self.load_footprints():
            logging.warn("No footprints loaded")
            notify("No footprints found.")
    
    def add_footprint(self, config):
        """ 
        This will create a saved footprint in the configuration store (cloudfiles)
        Returns True if creation was successful, otherwise False
        """
        logging.debug("add_footprint entered")
        notify("Adding footprint...")
        container = cf.get_container(self.container_name)
        try:
            index = self.container.get_object("index.json")
        except pyrax.exceptions.NoSuchObject, e:
            print "Creating empty index..."
            logging.info("Creating empty index")
            self.save()
            index = self.container.get_object("index.json")
        
        index = index.fetch()
        logging.info("loaded index %s" % index)
        logging.debug(config)
        logging.debug(self.footprints)
        self.footprints[config['footprint']] = config
        notify("Saving environment")
        self.save()
        # update the containers with the footprint metadata
        container_name = "%s-metadata" % config['footprint']
        try:
            fpcontainer = cf.get_container(container_name)
        except pyrax.exceptions.NoSuchContainer, e:
            logging.info("Container '%s' doesn't exist.  Creating."  % container_name)
            fpcontainer = cf.create_container(container_name)
        filename = "index.json"
        content = json.dumps(config)
        cf.store_object(fpcontainer, filename, content)
        logging.info("Footprint config %s saved" % container_name)
        notify("Footprint config %s saved" % container_name)
        return True
    
    def delete_footprint(self, footprint_name, force=False):
        """
        This will remove a footprint from the configuration, shutting it down first
        if necessary
        """
        
        # delete things in the container
        notify("Deleting footprint '%s'" % footprint_name)
        if not force:
            choice = "y"
            while choice.lower() not in ['y','n']:
                pass
                # choice = raw_input("Really destroy %s? [y/N] " % footprint_name).strip()
                # print "--%s--" % choice
            if choice != 'y':
                notify("Exiting")
                sys.exit()
        try:
            fp = self.get_footprint(footprint_name, start=False)
            fp.load(start=False)
            if fp.footprint_status == 'locked':
                notify("Footprint is locked.  use 'vcauto unlock %s' to unlock" % footprint_name)
                return False
            
            # shutdown machines and networks
            fp.stop()
            
            container = cf.get_container(fp.container_name)
            res = container.delete_all_objects()
            # print res
            container.delete()
            
        except pyrax.exceptions.NoSuchContainer:
            # *shrug*
            # already gone
            pass
        # delete the container
        # remove from environment footprint config
        print "Removing footprint configuration"
        del self.footprints[footprint_name]
        # save environment config
        self.save()
        
    def load_footprints(self):
        """
        checks for the existence of index.json in our container
        this should contain a list of the known environments
        """
        # container = self.cf.get_container(self.container_name)
        try:
            index = self.container.get_object("index.json")
        except pyrax.exceptions.NoSuchObject, e:
            logging.warning(e.message)
            index = None
            return False
            
        if index:
            logging.info("Loading index")
            self.footprints = json.loads(index.fetch())
            logging.debug(self.footprints)
            return True
                    
        # need to walk through a list of containers and grab their
        # index.json's
            
    def lock_footprint(self, fpname):
        """
        locks a footprint
        """
        fp = self.get_footprint(fpname, start=False)
        fp.lock()
        return True
        
    def unlock_footprint(self, fpname):
        fp = self.get_footprint(fpname, start=False)
        fp.unlock()
        return True
    
    def save(self):
        """
        serializes the list of known environments
        """
        logging.debug("environment save entered")
        filename = "index.json"
        content_dict = {}
        for fpname in self.footprints:
            # for now, just using the patteern ${footprint_name}-metadata for the name 
            content_dict[fpname] = fpname
        content = json.dumps(content_dict)
        index = cf.store_object(self.container, filename, content)        
        return True
        
    def start_footprint(self, footprint_name, monitor=True):
        """
        Starts up a new footprint; if the footprint has been saved, it
        will be started from its saved images; otherwise, initial config will be performed 
        using the standard Rackspace images
        """
        # FIXME
        # container name should be stored in index.json
        
        logging.debug("start_footprint entered")
        container_name = "%s-metadata" % footprint_name
        container = cf.get_container(container_name)
        index = container.get_object("index.json")
        config = json.loads(index.fetch())
        notify("Configuration loaded, starting footprint")
        logging.info("starting Footprint '%s'" % config["footprint"])
        # pprint.pprint(config)
        fp = Footprint(config)
        fp.load()
        if fp.footprint_status == 'locked':
            notify("Footprint is locked.  use 'vcauto unlock %s' to unlock" % footprint_name)
            return False
        
        
        # we now have a footprint with a valid configuration
        # we should probably check at this point whether the machines are actually running?
        
        # first, setup the networks...
        # Networks are no longer created by this script, 
        # they are managed as part of Rackconnect
        # fp.create_networks()
        # save the IDs, in case something happens to the machine setup
        fp.save()
        fp.create_machines()
        # FIXME: remove monitor flag? no longer checking
        fp.save()
        t = 0
        try:
            t = fp.monitor()
        except KeyboardInterrupt:
            print "\n"*len(fp.machines)
            pass
        
        print "Time elapsed: %s seconds" % str(int(t))
        
        for machine in fp.machines:
            server = fp.machines[machine]
            print "Setting password for %s" % machine
            try:
                server.set_password(fp.admin_password)
            except novaclient.exceptions.BadRequest:
                print "Couldn't set password for %s" % machine

        return True
        
    def show_footprint(self, fpname):
        """
        Returns metadata about a footprint.
        """
        logging.debug("show_footprint entered")
        # container_name = "%s-metadata" % footprint_name
        # container = self.cf.get_container(container_name)
        # index = container.get_object("index.json")
        # config = json.loads(index.fetch())
        # 
        # 
        # 
        # logging.info("loaded footprint configuration")
        # return config
        fp = self.get_footprint(fpname, start=False)
        pt = fp.status()
        print pt
    
    
    def suspend_footprint(self, fpname):
        """
        Saves to images, then stops
        """
        logging.info("Saving %s" % fpname)
        notify("Beginning suspend")
        fp = self.get_footprint(fpname)
        
        if fp.footprint_status == 'locked':
            notify("Footprint is locked.  use 'vcauto unlock %s' to unlock" % fpname)
            return False
        
        fp.save_to_images()
        res = fp.monitor_save()
        if res:
            # save was successful
            # try:
            #     raw_input("Press <enter> to shutdown footprint or ^C to cancel...")
            # except KeyboardInterrupt:
            #     print "Cancelled -- Exiting"
            #     sys.exit()
            fp.stop()
            notify("Cleaning up footprint %s" % fpname)
            self.cleanup_footprint(fpname)
            return True
        else:
            notify("Something went wrong with the save")
            return False
    
    def stop_footprint(self, fpname):
        """
        Stops a footprint.  Doesn't save beforehand...
        """
        logging.debug("%s entered" % __name__)
        fp = self.get_footprint(fpname, start=False)
        if fp.footprint_status == 'locked':
            notify("Footprint is locked.  use 'vcauto unlock %s' to unlock" % fpname)
            return False
        fp.stop()
    
    def cleanup_footprint(self, fpname):
        """
        Cleans up old images for a footprint
        """
        logging.debug("Environment: %s entered" % __name__)
        fp = self.get_footprint(fpname, start=False)
        fp.cleanup_old_images()
        fp.save()
        
    
    def get_footprint(self, fpname, start=True):
        """
        gets the named footprint
        """
        logging.debug("get_footprint entered")
        container_name = "%s-metadata" % fpname
        container = cf.get_container(container_name)
        index = container.get_object("index.json")
        config = json.loads(index.fetch())
        fp = Footprint(config)
        fp.load(start=start)
        return fp
        
    def dump_footprint(self, fpname):
        """
        shows the metadata of the named footprint
        """
        container_name = "%s-metadata" % fpname
        container = cf.get_container(container_name)
        index = container.get_object("index.json")
        config = json.loads(index.fetch())
        pprint.pprint(config)
        
    
class Machine(object):
    """
    Machines that make up Footprints
    """
    image_id = None
    uuid = None
    machine_name = None
    saved = False
    status = None
    flavor = None
    cloudserver = None
    networks = []
    images = []
    old_images = []
    # ip_adresses is in form of {netname:address}
    ip_addresses = {}
    # networks = []
    
    def __init__(self, footprint, mconf, name):
        """
        creates a machine in a footprint
        footprint is passed as an argument
        """
        logging.debug("%s entered __init__" % name)
        self.image_id = mconf["image-id"]
        self.networks = mconf["networks"]
        self.ip_addresses = mconf["ip-addresses"]
        self.flavor=mconf["flavor"]
        self.machine_name = "%s%s" % (footprint.footprint_name, name)
        self.footprint = footprint
        
    def isup(self):
        """
        If the machine is up and running, returns true.
        Otherwise, false
        """
        if self.cloudserver:
            # print self.cloudserver.status
            if self.cloudserver.status in ("ACTIVE",):
                return True
        
        return False
        
    def net_cmd(self):
        """
        creates the PowerShell snippet to setup the network
        """
        
        logging.debug("net_cmd called")
        cmd = ""
        # FIXME should probably grab the PrefixLength from the network definition
        # calc my router
        
        # FIXME: Need to split this into separate files...
        # files will be a dictionary of {"filename":"contents"}
        files = {}
        
        cmd = "rem cmd\r\n"
        tmpl = """netsh interface ip set address "%(nic)s" static %(v4_fixed_ip)s 255.255.255.0\r\n"""
        # FIXME: this should be read out of the configuration, probably
        nets = self.networks
        ips = self.ip_addresses 
        my_router = ""
        for netname in nets:
            v4_fixed_ip = ips.get(netname)
            my_net = v4_fixed_ip.split(".")[:3]
            my_net.append("254")
            my_router = ".".join(my_net)
            nic = "%s-%s" % (self.footprint.footprint_name, netname)
            logging.debug("Creating %s for %s" % (nic, nets))
            # net_id = self.networks.get(netname)
            cmd = cmd + tmpl % locals()
            
        cmd += """route -p add 192.168.1.0 MASK 255.255.255.0 %(my_router)s\r\n""" % locals()
        cmd += """route -p add 192.168.2.0 MASK 255.255.255.0 %(my_router)s\r\n""" % locals()
        cmd += """route -p add 192.168.3.0 MASK 255.255.255.0 %(my_router)s\r\n""" % locals()
        logging.debug("cmdfile:\n" + cmd)
        
        # print 50 * "x"
        # print cmd
        return cmd
    
    def load(self, uuid):
        """
        Loads a machine configuration from UUID
        """
        try:
            self.cloudserver = cs.servers.find(id=uuid)
        except novaclient.exceptions.NotFound, e:
            logging.warn("MACHINE LOAD: %s" % (e.message))
            self.cloudserver = None
    
    def create(self):
        """
        creates this
        """
        logging.debug("%s create called" % self)
        # find the image uuid from the image name
        img = self.footprint.images[self.image_id]
        machine_name = self.machine_name
        flavor = self.flavor
        nets = self.networks
        ips = self.ip_addresses
        # print "-- ips", ips
        nics = []
        # print "-- NETS", nets
        for nic in nets:
            # logging.info("%s: Adding network %s" % (machine_name, nets['nic'].id))
            # nics.append({"net-id":self.footprint.networks[nic].id, 'v4-fixed-ip':ips.get(nic)})
            nics.append({"net-id":self.footprint.networks[nic].id})
            
        if RACKCONNECT:
            logging.warn("Adding RackConnect address")
            nics.append({"net-id":cn.SERVICE_NET_ID})
        nics.append({'net-id' : cn.PUBLIC_NET_ID})
        cmd = self.net_cmd()
        # print "XXX:len(cmd)=%d" % len(cmd)
        files = {
            "c:\\cloud-automation\\bootstrap.cmd":cmd,
        }
        logging.info("Creating %s" % machine_name)
        notify("Creating %s" % machine_name)
        # cs is global pyrax.cloudservers
        logging.debug("-- " + str(machine_name) )
        logging.debug("-- " + str(img))
        logging.debug("-- " + str(flavor))
        logging.debug("-- " + str(nics))
        # this should work -> 
        srv = cs.servers.create(machine_name, img, flavor, nics=nics, files=files)
        self.cloudserver = srv
        logging.debug("creating machine, starting wait_for_build callback")

        pyrax.utils.wait_for_build(srv, callback=self.create_callback, interval=60)
        return True

    @property
    def id(self):
        """
        This returns the cloud UUID as a property
        """
        if self.cloudserver:
            return self.cloudserver.id
        else:
            return None
    @property
    def status(self):
        """
        returns a quick status line about this server
        """
        
        tmpl1 = """%-20s%-52s[%s]"""
        tmpl2 = """%-20s%-52s\n"""
        # print tmpl1 % ("Machine Name", "IP Addresses", "Status")
        # print 80 * "-"
        # print self.get_image()
        if self.cloudserver:
            # let's build the IPs first
            status = self.cloudserver.status
            
        else:
            status = "OFF"

        res2=""
        ip1 = "%s:%s" % (self.networks[0], self.ip_addresses[self.networks[0]])
        if len(self.networks) > 1:
            res2 += "\n"
            for network in self.networks[1:]:
                ipstr = "%s:%s" % (network, self.ip_addresses[network])
                res2+=tmpl2 % ("-", ipstr)
        # print res2
        # if len(self.ip_addresses.keys()) > 1:
        #     ip1 = self.ip_addresses.values()[0]
        res1 = tmpl1 % (self.machine_name, ip1, status)
        return res1 + res2
    
    def set_password(self, password):
        """
        sets the admin password via the Cloud API
        """
        self.cloudserver.change_password(password)
    
    @property
    def progress(self):
        """
        docstring for progress
        """
        if self.cloudserver:
            return self.cloudserver.progress
        else:
            return 0

    def get_image(self):
        """
        returns the image id for this server's image
        if no images are available, returns false
        """
        logging.debug("%s get_image entered" % str(self.machine_name))
        snapshots = cs.list_snapshots()
        # find the one for this server
        if self.cloudserver:
            server_id = self.cloudserver.id
        else:
            return self.image_id

        for snapshot in snapshots:
            img = snapshot.metadata.get("instance_uuid", None)
            # print "XXX:", img

            if img == server_id:
                print "Server %s has snapshot %s" % (server_id, img)
                return img

        print "Server %s has no snapshots" % (server_id)
        return None
        

    def get_progress(self):
        """
        hmm... workaround @progress not updating...
        """
        return self.cloudserver.progress
    
    def stop(self):
        """
        stops this machine
        """
        if self.cloudserver:
            logging.debug("stopping %s" % self.cloudserver)
            self.cloudserver.delete()
        else:
            try:
                logging.debug(self.cloudserver.status)
            except AttributeError: 
                logging.warn("%s not found" % self.machine_name)
            
    
    def create_image(self):
        """
        Creates an image of the machine's hard drive.
        Returns the UUID of the image
        """
        # FIXME: this needs to happen, like now.
        logging.debug("Machine.create_image entered")
        logging.debug("Old image: %s" % self.image_id)
        logging.info("Creating image of machine %s (%s)" % (self.machine_name, self.id))
        
        # create the image of the storage
        self.time_image_start = time.time()
        # logging.debug("Starting image...")
        # # m = self.machines[machine]
        # # img_id = m.create_image()
        # # image_map[machine] = img_id
        # self.cloudserver.create_image("%s_%s" % (self.machine_name, self.id), callback=create_image_callback)
        # # time_image_finish = time.time()
        # logging.debug("%s imaged to %s" % (self.machine_name, res.id))
        # elapsed = time_image_finish - time_image_start
        # logging.info("Image finished after %d seconds" % elapsed)
        # # update the configuration for this image
        if self.cloudserver:
            m = self.cloudserver
        else:
            logging.warn("Trying to create image for non-existent server %s" % str(self))
            return False
        try:
            logging.debug("starting image creation %s" % str(self))
            image_id = m.create_image("%s_%s" % (m.name, m.id))
            image =  cs.images.get(image_id)
            logging.debug("starting waiter thread for %s" % str(image))
            image = pyrax.utils.wait_until(image, "status", ["ACTIVE", "ERROR"], callback=self.create_image_callback, interval=60)

            logging.info("%s imaged to %s" % (m, image))
            #  elapsed = time_image_finish - time_image_start
            return image_id
        except novaclient.exceptions.Conflict, e:
            logging.debug(str(e))
            logging.warn("Image already in progress for %s" % str(self))
            return False
   
    def create_image_callback(self, obj):
        """docstring for create_image_callback"""
        logging.debug("create_image_callback entered for %s" % self.machine_name)
        # stop using the uuids, start using the image_map key
        # self.image_id = obj.id
        # logging.debug("adding %s to old images" % self.image_id)
        
        
        self.image_id = self.machine_name
        # notify("%s save finished" % self.machine_name)
        logging.debug("self.image_id: %s" % str(self.image_id))
        logging.debug(obj.id)
        time_image_finish = time.time()
        elapsed = time_image_finish - self.time_image_start
        logging.info("%s image finished in %s seconds" % (str(self.machine_name), str(elapsed)))
        self.footprint.save()
        self.saved = True
        
    def create_callback(self, obj):
        """
        used to monitor the progress of the cloud server build
        """
        logging.debug("%s create_callback entered" %  str(self.machine_name))
        # print "XXX:", obj
        self.completed = obj.progress
        self.cloudserver = obj
        self.uuid = self.cloudserver.id
        
        
    def list_images(self):
        """
        retrieves the list of images for this (active) machine
        """
        
        logging.debug("list_images entered for %s" % self.machine_name) 
        snapshots = cs.list_snapshots()
        res = []
        server_id = self.cloudserver.id
        # find the one for this server
        for snapshot in snapshots:
            img = snapshot.metadata.get("instance_uuid", None)
            # print img

            if img == server_id:
                print "Server %s has snapshot %s" % (server_id, img)
                res.append(img)

        return res
        
        
class Network(object):
    """Network object inside a footprint"""
    cloudnet = None
    def __init__(self, footprint, name):
        self.name = "%s-%s" % ( footprint.footprint_name, name)
        self.footprint = footprint
        
        # FIXME what's going on here?
        # try:
        #     self.load(footprint.infra["networks"][name])
        # except:
        logging.debug("couldn't load network, creating" + str(footprint.infra["networks"]))
        self.cidr = footprint.infra["networks"][name]["cidr"]
        
    
    def delete(self):
        """
        tears down the network
        """
        
        logging.info("Deleting network %s" % self.cloudnet)
        # res = cn.delete(self.cloudnet)
        res = self.cloudnet.delete()
        return res
    
    def stop(self):
        """
        stops the cloud network
        """
        logging.debug("Network.stop entered:" + str(self.id))
        # print self.cloudnet
        # res = cn.delete(self.cloudnet)
        notify("Stopping network %s" % self.name)
        # if not self.cloudnet:
        # 
        #   self.cloudnet = cn.find(id="52a24319-f58d-4795-a3bd-c22d87bb65ae")
        if self.cloudnet:
            res = self.cloudnet.delete()
        else:
            res = True
        return res
    
    def create(self):
        """
        creates the network, assigning myself a UUID
        if UUID exists, will try to load it from the saved file (in case the footprint is running)
        """
        logging.debug("%s create called" % self)
        # networks = self.infra.get("networks")
        notify("Creating network %s" % self.name)
        self.cloudnet = cn.create(self.name, cidr=self.cidr)
        return True
        
    def load(self, uuid, start=False):
        """
        creates a network object based on a UUID
        """
        try:
            self.cloudnet = cn.find(id=uuid)
        except pyrax.exceptions.NotFound:
            logging.debug("Net '%s' not found" % uuid)
            notify("Net %s not found" % uuid)
            if start:
                logging.info("Creating saved network %s" % str(self) )
                self.create()
            else:
                logging.info("Not creating network...")
            
        
    @property
    def id(self):
        """
        returns the ID of this network (property)
        """  
        if self.cloudnet:
            return self.cloudnet.id
        else:
            return None
             
class Footprint(object):
    """
    Footprints are groups of machines that are
    isolated in their own network.
    
    They can be created, deleted, shutdown, restarted
    """
    # infra is used to hold the yaml configuration 
    footprint_name = ""
    infra = None
    # networks holds a dictionary of networks, hashed by uuid
    networks = {}
    machines = {}
    # images is a dictionary of {image_name:image_uuid}
    images = {}
    savefile = None
    saved_images = {}
    old_images = []
    footprint_status = ""
    
    def __init__(self, config):
        """
        config is a dictionary containing footprint description
        """
        logging.info("Creating footprint")
        # self.infra = yaml.load(config)
        self.infra = config
        self.footprint_name = self.infra.get("footprint", "ehw")
        self.images = self.infra.get("images")
        self.old_images = self.infra.get("old_images", [])
        self.container_name = "%s-metadata" % self.footprint_name
        
        self.admin_password = self.infra.get('admin-password')
        self.savefile = self.infra.get("footprint", "outfile") + "-save.yaml"
        if os.path.exists(self.savefile):
            self.saved_images = yaml.load(open(self.savefile))
        self.footprint_status=self.infra.get("footprint_status", None)
        logging.debug("Loaded saved images: %s" % self.saved_images)
        # sys.exit(0)    
        
    def load_from_images(self):
        """
        loads a set of images back into the footprint
        needs to check and make sure the footprint doesn't exist
        """
        logging.debug("load_from_images called")
        return True
        
    
    def save_to_images(self):
        """
        saves current footprint to a set of images
        """
        
        logging.debug("save_to_images called")
        # return None
        notify("Saving to images")
        # first, create the images
        image_map = {}
        for machine in self.machines:
            logging.info("Creating image for %s" % machine)
            notify("Creating image for %s" % machine)
            m = self.machines[machine]
            img_id = m.create_image()
            logging.debug("machine: %s, img_id: %s" % (str(machine), str(img_id) ))

            old_img_id = self.images.get(m.machine_name, None)
            if old_img_id:
                logging.info("machine %s old image added to old_images %s " % ( str(machine), str(old_img_id) ))
                self.old_images.append(old_img_id)
            image_map[m.machine_name] = img_id
        
        # print image_map
        # FIXME: this needs to be updating the cloudfiles
        # savefile = open(self.savefile, 'w')
        # yaml.dump(image_map, savefile)
        # savefile.close()
        # print self.images
        # print image_map
        notify("Saving config")
        self.images = image_map
        self.save()
        
    def save(self, status=None):
        """
        saves profile of footprint to self.savefile
        savefile should be in the form of fpname-metadata/index.json in
        cloudfiles
        """ 
        logging.debug("%s Entered footprint save" % self)
        # save networks
        data = {}
        if status:
            data['footprint_status']=status
        else:
            data['footprint_status']=self.footprint_status
        data['footprint'] = self.footprint_name
        data['admin-password'] = self.admin_password
        data['images']=self.images
        data['networks'] = None
        data['servers'] = {}
        data['old_images'] = self.old_images
        
        networks = {}
        for network in self.networks:
            
            logging.debug("NETWORK:" + str(self.networks.get(network).id))
            networks[network] = {}
            networks[network]["uuid"] = self.networks.get(network).id
            networks[network]["cidr"] = self.networks.get(network).cidr
        data['networks'] = networks
        logging.debug(networks)

        for server in self.machines.keys():
            new_server = {}
            old_server = self.machines.get(server)
            logging.debug("SERVER: %s" % str(old_server))
            logging.debug("type(SERVER): %s" % type(old_server))
            new_server['image-id'] = old_server.image_id
            new_server['flavor'] = old_server.flavor
            new_server['uuid'] = old_server.id
            new_server['networks'] = old_server.networks
            new_server['ip-addresses'] = old_server.ip_addresses
            logging.debug(str(new_server))
            data['servers'][server] = new_server
            
        logging.debug("Getting list of containers")
        all_containers = cf.list_containers()
        
        if self.container_name in all_containers:
            logging.info("Container %s exists, opening" % self.container_name)
            mycontainer = cf.get_container(self.container_name)
        else:
            logging.warn("Container doesn't exist, creating...")
            mycontainer = cf.create_container(self.container_name)
        
        logging.debug("DATA:" + str(data))
        content = json.dumps(data)
        logging.debug("CONTENT:" + str(content))
        filename = "index.json"
        index = cf.store_object(mycontainer, filename, content)
        logging.debug("INDEX:" + str(index))
        
        logging.debug("DATA:" + str(data))
        content = json.dumps(data)
        logging.debug("CONTENT:" + str(content))
        filename = "state.json"
        index = cf.store_object(mycontainer, filename, content)
        logging.debug("INDEX:" + str(index))
        return True
        
    def load(self, start=False):
        """
        loads configuration from saved file in cloud
        if start = True (default), then networks and machines will be started
        """
        self.load_networks(start=start)
        self.load_machines(start=start)
        
    def load_machines(self, start=False):
        
        """
        Loads machines in this footprint from a saved configuration
        """
        logging.debug("%s load_machines entered" % self)
        all_containers = cf.list_containers()
        if self.container_name in all_containers:
            logging.info("Found existing container, checking for machine configuration")
            mycontainer = cf.get_container(self.container_name)
            try:
                index = mycontainer.get_object("index.json")
                mconf = json.loads(index.fetch())
                # print mconf
                for server in mconf['servers'].keys():
                    machine_name = server
                    logging.info("loading %s from file" % server)
                    new_machine = Machine(self, mconf['servers'][server], server)
                    if mconf['servers'][server].has_key("uuid"):
                        uuid = mconf['servers'][server]["uuid"]
                        new_machine.load(uuid)
                    self.machines[server] = new_machine
            except Exception, e:
                # print "ALJKALDFDKSJFLSKJDf"
                logging.warn(e.message)
                import traceback
                logging.debug(traceback.print_exc())
        # pprint.pprint(self.machines)
        return True
                
    def load_networks(self, start=False):
        """
        sets up networks based on a saved configuration
        """
        logging.debug("%s load_networks entered" % self)
        # networks = self.infra['networks']
        all_containers = cf.list_containers()
        if self.container_name in all_containers:
            logging.info("found existing container, checking for network configuration")
            mycontainer = cf.get_container(self.container_name)
            try:
                index = mycontainer.get_object("index.json")
                mconf = json.loads(index.fetch())
                for network in mconf['networks'].keys():
                    logging.info("loading %s from file" % network)
                    new_network = Network(self, network)
                    if mconf['networks'][network].has_key("uuid"):
                        uuid = mconf['networks'][network]["uuid"]
                        # print "YYY: ", uuid
                        new_network.load(uuid, start=start)
                    self.networks[network] = new_network
            except Exception, e:
                # print "ALJKALDFDKSJFLSKJDf"
                logging.warn(e.message)
                import traceback
                logging.debug(traceback.print_exc())
        
        # check if they exist...
        # for net in networks.keys():
        #     # create the network object
        #     new_net = Network(self, net)        
        # 
    def create_networks(self, force=False):
        """
        creates a network using the config file
        """
        # FIXME: debugging here
        logging.debug("create_networks called")
        # check for an existing configuration file...
        # logging.debug("networks: %s" %  self.infra.get("networks"))
        networks = self.infra.get("networks")
        for net in networks.keys():
            net_name = "%s-%s" % (self.footprint_name, net)
            cidr = self.infra['networks'][net]['cidr']
            uuid = self.infra['networks'][net].get("uuid", None)
            logging.info("Creating %s - %s" % (net_name, cidr))
            notify("Creating %s - %s" % (net_name, cidr))
            new_net = Network(self, net)
            if uuid:
                new_net.load(uuid, start=True)
            else:
                new_net.create()
            logging.debug(new_net)
            #print "Created network:", new_net  
            self.networks[net] = new_net
        notify("Finished creating networks")
        return True
    
    def delete_networks(self):
        """
        called when tearing down the environemnt
        """
        logging.debug("cleanup called")
        # for network in self.networks.key():
        #     self.networks[network].delete()
        for network in self.networks.values():
            logging.warn("Deleting network '%s'" % network)
            print "Deleting network '%s'" % network
            # print self.networks[network]
            network.delete()
        self.networks = {}
    
    def create_machines(self):
        """
        creates ALL the machines!
        
        At the end of this function, all machines should be in 
        either ACTIVE, BUILD, SPAWNING
        """
        logging.debug("create_machines called")
        machines = self.infra.get("servers")
        
        for machine in machines.keys():
            mconf = machines[machine]
            # see if the machine is already up and running
            # print mconf
            uuid = mconf.get("uuid", None) # this is a saved machine state
            machine_name = "%s%s" % (self.footprint_name, machine)
            new_machine = Machine(self, mconf, machine)
            if uuid:
                logging.info("Machine saved with ID:" + str(mconf.get("uuid")))
                new_machine.load(uuid)
                if new_machine.cloudserver:
                    logging.info("Found running server %s" % uuid)
                    continue
            
            logging.info("Creating machine %s" % machine)
            new_machine.create()

            self.machines[machine] = new_machine
            
    def delete_machines(self):
        """
        removes all the machines in this footprint.
        use with caution, obviously
        """
        logging.debug("delete_machines called")
        
        for machine in self.machines:
            logging.warn("Deleting %s" % machine)
            print "Deleting %s" % machine
            cs.servers.delete(self.machines[machine])
        
    def create_machine(self, mconf):
        """
        creates a machine using the dictionary 'mconf'
        Example:
        mconf = {
            flavor: 4,
            image-id: "d88188a5-1b02-4b37-8a91-7732e42348c1",
            networks: ['APP','FE','BE'],
        }
        """
        logging.debug("create_machine called")
        mconf = self.infra['servers'][machine]
        logging.debug( mconf)
        mnets = []
        for net in  mconf['networks']:
            net = self.footprint_name + net
            n = nets.get(net)
            mnets.extend(n.get_server_networks())
        res = cs.servers.create(machine, mconf.get("image-id"), mconf.get("flavor")) # , nics=mnets)

    def lock(self):
        """
        locks this footprint
        """
        logging.debug("%s lock called" % self.footprint_name)
        notify("Locking %s" % self.footprint_name)
        self.footprint_status = "locked"
        self.save()
        
    def unlock(self):
        """
        unlocks this footprint
        """
        logging.debug("%s unlock called" % self.footprint_name)
        notify("Unlocking %s" % self.footprint_name)
        self.footprint_status = "unlocked"
        self.save()
        
    def cleanup(self):
        """
        tears down the environment
        """
        logging.debug("cleanup called")
        self.delete_networks()
        self.delete_machines()
        
    def fp_meta(self):
        """
        prints metadata about the footprint
        """
        for server in self.machines:
            s = self.machines[server]
            print "%s: %s (%s)" % (s.id, s.adminPass, s)
            
    def initialize_environment(self):
        """
        sets up an environment from scratch, using the configuration 
        file 
        """
        logging.debug("initialize_environment called")
        try:
            # logging.info("Creating networks...")
            self.create_networks()
            self.create_machines()
            self.save()
        except Exception, e:
            # something went wrong with the creating of the networks
            logging.warn("Exception encountered")
            import traceback
            logging.debug(traceback.print_exc())
            raise e
        return True
        
    def monitor(self):
        """
        shows a table with current operations and their progress
        """
        logging.debug("monitor entered")
        # monitor machines...
        # first, get a list of machine IDs
        res = progress_table(self.machines)
        return res

    def stop(self):
        """
        Stops my running machines and Networks
        """
        logging.debug("footprint/stop entered")
        logging.info("Stopping cloud instances")
        print "Stopping machines"
        for machine in self.machines:
            logging.debug("stopping %s" % machine)
            server = self.machines[machine]
            server.stop()
        
        # monitor until all the machines are down
        active_machines = 1
        while active_machines:
            running = 0
            active_machines = 0
            for machine in self.machines:
                server = self.machines[machine]
                try:
                    tmp = cs.servers.get(self.machines[machine].id)
                    active_machines = 1
                    running = running + 1 
                except novaclient.exceptions.NotFound:
                    continue
            # if running == 0:
            #     break
            time.sleep(10)
            sys.stdout.write(".")
            sys.stdout.flush()
            
        logging.info("Stopping Networks")
        print
        print "Stopping networks"
        
        for network in self.networks:
            logging.debug("stopping %s" % str(network))
            n = self.networks[network]
            n.stop()
            
        while True:
            running = 0
            # print self.networks
            for network in self.networks:
                n = self.networks[network]

                try:
                    tmp = cn.find(id=n.id)
                    running = running + 1
                except pyrax.exceptions.NotFound:
                    continue
            if running == 0:
                break
            time.sleep(1)
            sys.stdout.write(".")
            sys.stdout.flush()
        

    def cleanup_old_images(self):
        """
        gets rid of the images that are in self.old_images
        """
        
        logging.debug("%s cleanup_old_images entered" % self.footprint_name)
        active_imgs = self.images.values()
        old_images = self.old_images[:]
        for img_id in old_images:
            logging.info("Deleting image %s from footprint %s" % (img_id, self.footprint_name))
            if img_id not in active_imgs:
                notify("Deleting image %s from footprint %s" % (img_id, self.footprint_name))
                img = cs.images.get(img_id)
                if img:
                    try:
                        img.delete()
                    except novaclient.exceptions.NotFound:
                        notify("Couldn't find image %s" % img_id)
                self.old_images.remove(img_id)
            else:
                notify("Not deleting active image %s" % img_id)
        # save changes
        self.save()
        
    def status(self):
        """
        shows the status of networks / machines
        """
        logging.debug("%s entered status" % self)
        # print_config(self.infra)
        # print self.images
        # headers = ["Machine Name", "Flavor", "IP Addresses", "Image Name", "Status"]
        # pt = prettytable.PrettyTable(headers)
        # pt.align["Machine Name"]="l"
        # pt.align["IP Addresses"] = "l"
        # pt.align["Image Name"] = "l"
        # pt.align["Status"] = "r"
        
        print "Checking status of %s" % self.footprint_name
        # tmpl = "%(machine_name)-20s%(flavor)5s%(status)-30s"
        tmpl1 = """%-20s%-52s[%s]"""
        tmpl2 = """%-20s%-60s\n"""
        print tmpl1 % ("Machine Name", "IP Addresses", "Status")
        print 80 * "-"
        
        for machine in self.machines.keys():
            m = self.machines[machine]
            # machine_name = m.machine_name
            # ips = str(m.ip_addresses)
            # flavor = str(m.flavor)
            # img = str(m.image_id)
            # status = str(m.status)
            # pt.add_row([m, ips, status, img, status])
            # print "FFF", m, ips, flavor, img, status
            # print tmpl % locals()
            print m.status
            
        return "%s is currently: %s" % (self.footprint_name, self.footprint_status)
      
      
    def monitor_save(self):
        """
        monitors the progress of an image save
        """
        logging.debug("%s monitor_save entered" % str(self))
        finished = 0
        old_finished = 0 # used for notify
        while True:
            finished=0
            for machine in self.machines.keys():
                m = self.machines[machine]
                if m.saved:
                    finished += 1
                    if finished > old_finished:
                        logging.info("Finished saving %s" % str(m.machine_name))
                        notify("Finished saving: %d/%d" % (finished, len(self.machines.keys())))
                        old_finished = finished
            if finished >= len(self.machines.keys()):
                notify("All done")
                break
            time.sleep(5)
        print "%d machines saved" % finished
        return True
        

def progress_table(machine_list):
    """
    takes 'func' as a method to return a list of state values
    FIXME: this currently does a pretty expensive poll of the running servers
    """
    # go into a loop
    # print machine_list
    finished = 0
    # calculate max name length
    cs_dict = {}
    # welp, maybe benerate a new list of servers? referencing problems seem
    # to be causing the progress to not update
    
    for machine in machine_list:
        try:
            cs_dict[machine] = cs.servers.find(id=machine_list[machine].id)
        except novaclient.exceptions.NotFound:
            cs_dict[machine] = None
    
    cs_dict = machine_list
    
    while True:
        name_len = 0
        # machines = cs.list()
        # machines = machine_list
        # format the columns for the longest names
        for machine in cs_dict:
            m = cs_dict[machine]
            if len(m.machine_name) > name_len:
                name_len = len(m.machine_name)
        tmpl = "%%-%ds:[%%s][%%4s%%%%]\n" % name_len
        term_width = 80
        hash_len = term_width - 2 - name_len 
        # lines, cols = struct.unpack('hh',  fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, '1234'))
        
        # print "-" * cols
        
        # create a hash of cloud_servers
            
        
        
        # create the table
        finished = 0
        num_servs = len(cs_dict)
        for machine in cs_dict:
            # states[i] = states[i] + random.random()
            m = cs_dict[machine]
            progress = m.progress
            if progress >= 100:
                finished += 1
            num_hashes = int(round(progress/100.0 * hash_len))
            num_blanks = hash_len - num_hashes
            pstring = int(num_hashes) * "#" + int(num_blanks) * " "
            sys.stdout.write(tmpl % (m.machine_name, pstring, progress))
            sys.stdout.flush()
        if finished == len(cs_dict):
            return time.time() - start_time
        sys.stdout.write("%d seconds\n" % (time.time() - start_time))
        sys.stdout.write("%c[%dA" % (27, num_servs+1))
        sys.stdout.flush()
        time.sleep(5)
        #
        # move the cursor up len(states.keys()) rows


def find_image(image_name):
    """
    resolves an image_name to an image
    """
    imgs = pyrax.images
    image = imgs.list(name=image_name)[0]

    # print image.id
    return image.id
    

        
    

def generate_config(fpname=None, filename=None, image=None):
    """docstring for generate_config"""
    logging.debug("entering generate_config")
    if not fpname:
        print "Please provide a name for this footprint"
        sys.exit(1)
    filename = filename or "%s.yaml" % fpname
    logging.debug("Using config filename: %s " % filename)
    if os.path.exists(filename):
        print 
        answer = raw_input("File '%s' exists. Overwrite, cancel o? [Y/n] " % filename)
        answer.strip()
        if answer.lower() in ["yes", "y"]:
            print "Going to overwrite "
        else:
            print "Not overwriting "
            # sys.exit(0)
        print "jk/lol"
    admin_pass_1 = "a"
    admin_pass_2 = "b"
    while admin_pass_1 != admin_pass_2:
        admin_pass_1 = getpass.getpass("Please enter an Admin password for this cluster: ")
        admin_pass_2 = getpass.getpass("Please re-enter the password to confirm: ")
    
    admin_pass = admin_pass_1
    # FIXME: create an external template, cowboy
    tmpl="""
images:
    sql: 
    dotnet: 
    vyatta: 

footprint: %(fpname)s
admin-password: %(admin_pass)s
networks:
  FE:
    cidr: 192.168.1.0/24
  AP:
    cidr: 192.168.2.0/24
  DB:
    cidr: 192.168.3.0/24
servers:
    WAF:
        flavor: 3
        image-id: vyatta
        networks: [AP,FE,DB]
        ip-addresses:
            FE: 192.168.1.254
            AP: 192.168.2.254
            DB: 192.168.3.254
    KED1AP01:
        flavor: 4
        image-id: dotnet 
        networks: [AP,]
        ip-addresses:
            AP: 192.168.2.10
    KED1WB01:
        flavor: 4
        image-id:  dotnet
        networks: [FE,]
        ip-addresses:
            FE: 192.168.1.10
    KED1EI01:
        flavor: 4
        image-id:  dotnet
        networks: [FE,]
        ip-addresses:
            FE: 192.168.1.11
    KED1MQ01a:
        flavor: 4
        image-id:  dotnet
        networks: [FE,]
        ip-addresses:
            FE: 192.168.1.12
    KED1DB01a:
        flavor: 5
        image-id: sql 
        networks: [DB,]
        ip-addresses:
            DB: 192.168.3.10
    KED1DB02a:
        flavor: 5
        image-id: sql 
        networks: [DB,]
        ip-addresses:
            DB: 192.168.3.11        
    KED1DB03a:
        flavor: 5
        image-id:  sql
        networks: [DB,]
        ip-addresses:
            DB: 192.168.3.12
    KED1DB04a:
        flavor: 5
        image-id:  sql
        networks: [DB,]
        ip-addresses:
            DB: 192.168.3.13

"""
    config = tmpl % locals()
    i = 1
    while os.path.exists(filename):

        basename, extension = os.path.splitext(filename)
        filename_tmpl = "%s-%02d%s"
        backup_filename = filename_tmpl % (basename, i, extension)
        if os.path.exists(backup_filename):
            logging.debug("%s exists, continuing" % backup_filename)
            i = i + 1
            continue
        logging.info("Backing up %s -> %s" % (filename, backup_filename))
        os.rename(filename, backup_filename)
    
    fd = open(filename, "w")
    fd.write(config)
    fd.close()
    
    
    
    
    
    
def make_parser():
    """
    sets up the command-line parser
    """
    parser = argparse.ArgumentParser(description="Manage development Footprints in Rackspace Cloud")
    parser.add_argument("--username", metavar="<rackspace_username>", help="Username for the Rackspace API")
    parser.add_argument("--password", metavar="<rackspace_apikey>", help="API Key for the Rackspace API")
    
    subparsers = parser.add_subparsers(dest="subparser_name")
    
    # create 
    parser_create =  subparsers.add_parser('create', help="Create a footprint")
    # parser_create.add_argument("-n", "--name", metavar="<footprint_name>", help="Name of Footprint to create") 
    parser_create.add_argument("configfile", metavar="<filename>", help="Name of configuration file")
    
    # start
    parser_start =  subparsers.add_parser('start', help="Start a footprint")
    parser_start.add_argument("name", metavar="<footprint_name>", help="Name of Footprint to start") 
    parser_start.add_argument("-m", "--monitor", action="store_true", help="Monitor Footprint operations")
    
    # list
    parser_list = subparsers.add_parser('list', help="List footprints")
    # parser_list.add_argument("-i", "--uuid", help="UUID of footprint")
    
    # destroy 
    parser_destroy = subparsers.add_parser('destroy', help="Destroy VMs, networks, and saved images associated with a footprint")
    # parser_destroy.add_argument("--id", "-i", metavar="<uuid>", help="UUID of a footprint")
    parser_destroy.add_argument("-m", "--monitor", action="store_true", help="Monitor progress of footprint destruction")
    parser_destroy.add_argument("name", metavar="<footprint_name>", help="Name of Footprint to destroy")
    parser_destroy.add_argument("-f", "--force", action="store_true", help="Destroy without confirmation")
    
    # suspend 
    parser_suspend = subparsers.add_parser('suspend', help="Save VM images of a footprint and shuts down VMs")
    # parser_suspend.add_argument("-i", '--uuid', metavar="<uuid>", help="UUID of a footprint to suspend")
    parser_suspend.add_argument("name", metavar="<footprint_name>", help="Name of footprint to be suspended")
    # parser_suspend.add_argument('-m', '--monitor', action="store_true", help="Monitor suspending of footprint")
    
    # save 
    parser_save = subparsers.add_parser('save', help="Saves profile of an existing environment")
    # parser_save.add_argument("-i", "--uuid", metavar="<uuid>", help="UUID of a footprint to save")
    parser_save.add_argument("name", help="Name of footprint to save", metavar="<footprint>")
    
    # monitor 
    parser_monitor = subparsers.add_parser('monitor', help="Monitor an environment until everything settles")
    parser_monitor.add_argument("name", help="Name of footprint", metavar="<footprint>")
    
    
    # parser_restore = subparsers.add_parser('restore', help="Create a running environment from saved images")
    # parser_restore = subparsers.add_parser('monitor', help="Monitor a running environment's status")
    # parser_restore.add_argument("--uuid", metavar="<uuid-of-environment>", help="ID of environment to restore (see 'list' command)")
    parser_status =  subparsers.add_parser('status', help="Show the status of an environment")
    parser_status.add_argument("name", nargs="?")
    
    # generate-config
    parser_generate_config =  subparsers.add_parser('generate-config', help="Show the status of an environment")
    parser_generate_config.add_argument("-f", "--filename", help="Filename for configuration file",  )
    parser_generate_config.add_argument("-n", "--name", help="Short name for new footprint",  )
    parser_generate_config.add_argument("-i", "--image", help="Base image UUID for footprint",)
    
    # show
    parser_show = subparsers.add_parser("show", help="Show data about an environment")
    parser_show.add_argument('name', help="Name of footprint", metavar="<footprint>")
    
    # cleanup
    parser_cleanup = subparsers.add_parser("cleanup", help="Remove networks and images that are no longer relevant")
    parser_cleanup.add_argument('name', help="Name of footprint", metavar="<footprint>")
    
    
    # dump
    parser_dump = subparsers.add_parser("dump", help="Dump configuration data for an environment")
    parser_dump.add_argument('name', help="Name of footprint", metavar="<footprint>")
    

    # stop
    parser_stop = subparsers.add_parser("stop", help="Stop a running footprint")
    parser_stop.add_argument("name", help="Name of footprint", metavar="<footprint>")

    parser_lock = subparsers.add_parser("lock", help="Lock a footprint (prevents shutdown / startup)")
    parser_lock.add_argument("name", help="Name of footprint", metavar="<footprint>")

    parser_unlock = subparsers.add_parser("unlock", help="Unlock a footprint (allows shutdown / startup)")
    parser_unlock.add_argument("name", help="Name of footprint", metavar="<footprint>")
    
    
    return parser

def print_config(config):
    """
    creates a nice table for a configuration object
    """
    # pprint.pprint(config)
    headers = [u'name', u'flavor', u'ip-addresses', u'image-id']
    pt = prettytable.PrettyTable(headers)
    pt.align["name"] = 'l'
    pt.align["flavor"] = 'l'    
    for s in config["servers"]:
        server = config["servers"][s]
        tds = []
        tds.append(s)
        tds.append(server['flavor'])
        # make a nice list of networks:
        nets = ""
        for ip in server['ip-addresses'].keys():
            nets = nets + "%s: %s\n" % (ip, server['ip-addresses'][ip])        
        tds.append(nets)
        tds.append(server['image-id'])
        
        pt.add_row(tds)
    print pt.get_string()



if __name__=='__main__':
    # setup command-line arguments
    parser = make_parser()
    args = parser.parse_args()
    # configfile = args.configfile
    notify("Starting up...")
    # order is command line; 
    if args.username:
        username = args.username
    elif os.environ.get("OS_USERNAME", None):
        logging.debug("Username not provided on command line, trying environment")
        username = os.environ.get("OS_USERNAME")
    else:
        logging.debug("Username not found in environment. Asking for manual input.")
        username = raw_input("Rackspace user name:").strip()
    logging.info("Connecting with username: %s" % username)
    notify("Connecting with username: %s" %username)

    if args.password:
        password = args.password
    elif os.environ.get("OS_PASSWORD", None):
        logging.debug("Password not provided on command line, trying environment")
        password = os.environ.get("OS_PASSWORD")
    else:
        import getpass
        logging.debug("Password not found in environment. Asking for manual input.")
        password = getpass.getpass("Rackspace Password:")

    pyrax.set_setting("identity_type", "rackspace")
    pyrax.set_credentials(username, password)

    cn = pyrax.cloud_networks
    cs = pyrax.cloudservers
    cf = pyrax.cloudfiles
    # find_image("Windows Server 2008 R2 SP1")
    notify("Connected to Rackspace Cloud")

    e = Environment()
    
    if args.subparser_name == "status":
        logging.debug("status passed")
        if args.name:
            fps = [args.name]
        else:
            fps = e.footprints
        
        for footprint in fps:
            e.show_footprint(footprint)
    
    if args.subparser_name == "generate-config":
        logging.debug("generate-config passed")
        generate_config(fpname=args.name, filename=args.filename, image=args.image)
        sys.exit(0)
        
    if args.subparser_name == "list":
        print "Listing footprints"
        for fpname in e.footprints:
            print "-", fpname
        sys.exit(0)

    if args.subparser_name == "dump":
        logging.info("Dumping footprint config for %s" % args.name)
        e.dump_footprint(args.name)
        sys.exit(0)

    if args.subparser_name == "cleanup":
        logging.info("Dumping footprint config for %s" % args.name)
        e.cleanup_footprint(args.name)
        sys.exit(0)

    if args.subparser_name == "show":
        # print args
        logging.info("Attempting to show footprint %s" % args.name)
        e.show_footprint(args.name)
        # e.dump_footprint(args.name)
        # pprint.pprint(config)
        # print_config(config)
        sys.exit(0)


    if args.subparser_name == "create":
        # going to create a footprint
        logging.info("Loading configuration from '%s'" % args.configfile)
        configfile = args.configfile
        if configfile:
            config = yaml.load(open(configfile))
        logging.debug("Using configuration:" + str(config))
        e.add_footprint(config)
        sys.exit(0)

    if args.subparser_name == "start":
        logging.info("Attempting to start footprint %s (monitor=%s)" % (args.name, args.monitor))
        notify("Starting footprint %s" % (args.name))
        e.start_footprint(args.name, args.monitor)
        sys.exit(0)
        
    if args.subparser_name == "monitor":
        logging.info("Attempting to monitor")
        fpname = args.name
        # FIXME: need to make this fp-specific
        # progress_table(cs)
        fp = e.get_footprint(fpname)
        fp.monitor()
        sys.exit(0)
        
    if args.subparser_name == "stop":
        logging.info("Stopping footprint")
        fpname = args.name
        # FIXME: add confirmation message
        # FIXME: check for lock that would prevent it shutting down
        e.stop_footprint(fpname)
            
    if args.subparser_name == "destroy":
        logging.info("Destroying footprint")
        fpname = args.name
        # sys.exit()
        e.delete_footprint(fpname, force=args.force)
        
    if args.subparser_name == "suspend":
        logging.info("Suspending footprint")
        logging.info("Creating images...")
        fpname = args.name
        e.suspend_footprint(fpname)
        
    if args.subparser_name == "lock":
        fpname = args.name
        logging.info("Locking footprint %s" % fpname)
        e.lock_footprint(fpname)

    if args.subparser_name == "unlock":
        fpname = args.name
        logging.info("Unlocking footprint %s" % fpname)
        e.unlock_footprint(fpname)
