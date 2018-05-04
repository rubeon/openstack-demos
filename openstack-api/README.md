Rackspace Cloud Automation
=========================

Objectives
----------

The Cloud Automation project's target is to provide:

- A cloud-based architecture for the customer's development environments
- Allowing the customer to manage sets of Cloud guests in Rackspace's public cloud
- Procedures to easily and reliably create, image, and destroy development environments, known as Footprints

Purpose
-------

The purpose of the project is to provide agility and cost-savings for the customer's developments efforts.  New cloud images can be create via simple commands, and the deployment of these images can be replicated for different teams and uses inside the Rackspace Public Cloud.

Usage
-----

Environments can be created, imaged, and destroyed by running the commands below.

**create:** Create the environment specified by the configuration file `footprintname.yaml`:

    vcauto create -f configfile.yaml 
    
**list** Lists all footprints

    vcauto list
    
**save**: Create snapshot images of the cloud servers belonging to footprint

    vcauto save footprintname

**destroy**: Completely destroy footprint; delete images; and shut down running cloud servers belonging to footprint. Remove configuration for footprint as well 

**USE WITH CAUTION**!
    
    vcauto destroy footprintname

**monitor**: Monitor operations being performed on the servers belonging to footprint
    
    vcauto monitor footprintname
    
**start**: Start networks and machines belonging to footprint
    vcauto start footprintname

**stop**: Stop servers belong to a footprint and shut down networks

    vcauto stop footprintname

**suspend**: First save server images, then suspend them

    vcauto suspend footprintname

**status**: Show the current status of a footprint    
    
    vcauto status footprintname
    
**show**: Show the configuration of a footprint

    vcauto show  footprintname

Authentication
--------------

The `vcauto` automation script relies on the standard environment variables used by the `nova` OpenStack client. The following document describes how to find and use the environment variables:


    http://docs.rackspace.com/servers/api/v2/cs-gettingstarted/content/gs_env_vars_summary.html
    
The following environment variables the minimal required for using `nova` and `vcauto` and can be stored in ~/.novarc:

    OS_USERNAME=CPLoginName (e.g., "customer-cloud")
    OS_TENANT_NAME=Acct#
    OS_TENANT_ID=${OS_TENANT_NAME}
    OS_AUTH_SYSTEM=rackspace
    OS_PASSWORD=<apikey>
    OS_AUTH_URL=https://lon.identity.api.rackspacecloud.com/v2.0/
    OS_REGION_NAME=LON
    export OS_USERNAME OS_TENANT_NAME OS_AUTH_SYSTEM OS_PASSWORD OS_AUTH_URL OS_REGION_NAME OS_NO_CACHE HEAT_URL

Configuration
-------------

Footprints are configured in a YAML-formatted configuration file.  When creating a footprint, pass the path to this file to the `create` command:

    vcauto create configfile.yaml

Once created, the yaml file is not longer used.  It may be used to re-create the 

Requirements
------------

* pyrax
* PyYAML

Workflow
=======

Setting up an Initial Footprint Configuration

Finding the the right Rackspace base image  
------------------------------------------

On a system configured to use Rackspace's Nova API, use `nova image-list` to find the ID of the master images:

```bash
$ nova image-list|grep dotnet
| 96b04cf7-b25f-43a5-ad86-da89fd75f619 | cust-dotnet [...]
$ nova image-list|grep sql
| bd059afe-3023-4c70-8e59-b3e7738e4d8a | cust-sql [...]
```

In this case, we'll be using the two master images, cust-dotnet and cust-sql. These images were created as Gold Master images.

Defining the Networks
---------------------

In our initial spec, we'll be using three isolated networks:

1. FE (front-end): 192.168.1.0/24
2. AP (application): 192.168.2.0/24
3. BE (backend): 192.168.3.0/24

Defining the servers
--------------------

We'll be using the following server names for our machines. These are configurable.

1.    KED1AP01
2.    KED1DB01a
3.    KED1DB02a
4.    KED1DB03a
5.    KED1DB04a
6.    KED1EI01
7.    KED1MQ01a
8.    KED1WB01

Naming the Footprint
--------------------

A footprint's name should be a 1- or 2-character name.  This will be prefixed to all the footprint's networks and cloud server instance names, so make sure it's recognizable.

Creating a Footprint
--------------------

Creating a new Footprint is a two-step process:

- Generate the configuration file  using the `generate-config` command

    vcauto generate-config --filename myfootprint.yaml --name myfootprint

- After inspecting the footprint.yaml file, create the footprint with the `create` command

    vcauto create myfootprint.yaml

The footprint will now appear in the list of available footprints:

    vcauto list
    Listing footprints:
    - myfootprint

This footprint is now available for the vcauto application.

    images:
        sql: 9ffb0897-f932-4f11-8851-5ad1adabbdaf
        dotnet: 397944e4-ce5e-44b5-bf8f-4a2e759a0640
        vyatta: 107cbb76-fa23-4dda-ac1a-505fe88bc1e2

    footprint: RC
    admin-password: Arpanet1
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

Scheduling footprint start and stop
-----------------------------------

Footprints can be suspended and started from the command line using the `vcauto` command as detailed above.

Additionally, the system facility `cron` can be used to schedule stopping and starting of footprints. 

The following crontab will start a footprint at 6AM and suspend it at 7PM:

    # start at 6:00AM
    0 6 * * * . ~/.novarc; vcauto start footprint_name
    # suspend at 7:00PM
    0 19 * * * . ~/.novarc; vcauto suspend footprint_name

The crontab can be edited using the command `crontab -e`. 

More information about configuring crontabs can be found in the man page for crontab, accessed by the command `man 5 crontab`.
    
**Considerations**

* The time provided is the console machine's local time, currently configured for London time

* The Rackspace credentials file ~/.novarc needs to be included as shown on the cron command line. This allows the vcauto command to talk to the Rackspace API endpoints

* Locking will prevent the commands from changing the state of the footprints

Creating A New Footprint from Gold Images
-------------------------------------

Footprints are built from server images.  Once you have a set of images that have been configured to the build specification, the next step is to create a set of images based off those servers.

Creating images can be accomplished either via the My Cloud portal at Rackspace, or via the `nova image-create` command.

Once the images have been created, create a new configuration file listing the required servers and the images that should be used for them.

The configuration file can be creating using the following command:

    vcauto generate-config -n footprint_name

The file will be called footprint_name.yaml by default.

In our proof of concept, we had the following servers:

1. WAF
1. KED1AP01
1. KED1WB01
1. KED1EI01
1. KED1MQ01a
1. KED1DB01a
1. KED1DB02a
1. KED1DB03a
1. KED1DB04a

In our configuration file, we supplied a list of image names and the Rackspace Cloud UUIDs for these image names.  Once these are defined, the image name should be used in the configuration file to define a server's base image:

    images:
        sql: ffa476b1-9b14-46bd-99a8-862d1d94eb7a
    
    ...
    
    KED1DB04a:
        flavor: 5
        image-id:  sql
        networks: [DB,]
        ip-addresses:
            DB: 192.168.3.13
    
Once the configuration has been finished, the `vcauto` utility can be used to post the configuration into Rackspace Cloud:

    vcauto create footprint_name.yaml
    
Confirm the configuration:

    vcauto show footprint_name
    vcauto dump footprint_name
    
Start the new footprint:

    vcauto start footprint_name
    ...
