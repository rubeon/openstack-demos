#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: powerdns_record
short_description: Manage PowerDNS records
description:
- Create, update or delete a PowerDNS records using API
- A record is unique identified by name and type
- Changing a records type is therefore not possible
options:
  content:
    description:
    - Content of the record
    - Could be an ip address or hostname
  name:
    description:
    - Record name
    - If name is not an FQDN, zone will be added at the end to create an FQDN
    required: true
  server:
    description:
    - Server name.
    required: false
    default: localhost
  ttl:
    description:
    - Record TTL
    required: false
    default: 86400
  type:
    description:
    - Record type
    required: false
    choices: ['A', 'AAAA', 'CNAME', 'MX', 'PTR', 'SOA', 'SRV']
    default: None
  zone:
    description:
    - Name of zone where to ensure the record
    required: true
  pdns_host:
    description:
    - Name or ip address of PowerDNS host
    required: false
    default: 127.0.0.1
  pdns_port:
    description:
    - Port used by PowerDNS API
    required: false
    default: 8081
  pdns_prot:
    description:
    - Protocol used by PowerDNS API
    required: false
    default: http
    choices: ['http', 'https']
  pdns_api_key:
    description:
    - API Key to authenticate through PowerDNS API
author: "Thomas Krahn (@nosmoht)"
'''

EXAMPLES = '''
- powerdns_record:
    name: host01.internal.example.com
    type: A
    content: 192.168.1.234
    state: present
    zone: internal.example.com
    pdns_host: powerdns.example.cm
    pdns_port: 8080
    pdns_prot: http
    pdns_api_key: topsecret
'''

import requests
import logging

try:
    import http.client as http_client
except ImportError:
    # Python 2
    import httplib as http_client

http_client.HTTPConnection.debuglevel = 1

logging.basicConfig(filename='/tmp/powerdns_record.log')
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True


class PowerDNSError(Exception):
    def __init__(self, url, status_code, message):
        self.url = url
        self.status_code = status_code
        self.message = message
        super(PowerDNSError, self).__init__()


class PowerDNSClient:
    def __init__(self, host, port, prot, api_key):
      
        self.url = '{prot}://{host}:{port}'.format(prot=prot, host=host, port=port)
        self.headers = {'X-API-Key': api_key,
                        'content-type': 'application/json',
                        'accept': 'application/json'
                        }

    def _handle_request(self, req):
        logging.info("_handle_request entered")
        logging.info("_handle_request req: \n%s", str(req.text))
        logging.info("_handle_request status_code: req.status_code %s", req.status_code)
        if req.status_code in [200, 201, 204]:
            return json.loads(req.text)
        elif req.status_code == 404:
            logging.info("_handle_request 404") 
            error_message = 'Not found'
        else:
            logging.info("_handle_request fallthrough, req=%s", req)
            error_message = self._get_request_error_message(data=req)

        raise PowerDNSError(url=req.url,
                            status_code=req.status_code,
                            message=error_message)

    def _get_request_error_message(self, data):
        logging.info("_get_request_error_message entered") 
        request_json = data.json()
        logging.info("_get_request_error_message data: %s", str(request_json))
        if 'error' in request_json:
            logging.info("_get_request_error_message 'error' in request_json")
            request_error = request_json.get('error')
        elif 'errors' in request_json:
            logging.info("_get_request_error_message 'errors' in request_json")
            request_error = request_json.get('errors')
        else:
            logging.info("_get_request_error_message no error message found")
            request_error = 'No error message found'
        return request_error

    def _get_zones_url(self, server):
        logging.info("_get_zones_url entered")
        return '{url}/servers/{server}/zones'.format(url=self.url, server=server)

    def _get_zone_url(self, server, name):
        logging.info("_get_zone_url entered")
        return '{url}/{name}'.format(url=self._get_zones_url(server), name=name)

    def get_zone(self, server, name):
        logging.info("get_zone entered")
        req = requests.get(url=self._get_zone_url(server, name), headers=self.headers)
        logging.info("get_zone data: %s", str(req.json()))
        
        if req.status_code == 422:  # zone does not exist
            logging.warn("get_zone: Returning None")
            return None
        logging.info("get_zone: req")
        return self._handle_request(req)

    def get_record(self, server, zone, name):
        # TODO: implementation
        logging.info("get_record entered")
        return dict()

    def _get_request_data(self, changetype, server, zone, name, rtype, content=None, disabled=None, ttl=None):
        logging.info("_get_request_data entered")
        logging.info("_get_request_content: %s", str(content))
        record_content = list()
        record_content.append(dict(content=content, disabled=disabled))
        record = dict(name=name, type=rtype, changetype=changetype, records=record_content, ttl=ttl)
        logging.info("_get_request_data record: %s", str(record))
        rrsets = list()
        rrsets.append(record)
        logging.info("_get_request_data rrsets: %s", str(rrsets))
        data = dict(rrsets=rrsets)
        logging.info("_get_request_data data: %s", str(data))
        return data

    def create_record(self, server, zone, name, rtype, content, disabled, ttl):
        logging.info("create_record entered")
        url = self._get_zone_url(server=server, name=zone)
        data = self._get_request_data(changetype='REPLACE', server=server, zone=zone, name=name, rtype=rtype,
                                      content=content, disabled=disabled, ttl=ttl)
        req = requests.patch(url=url, data=json.dumps(data), headers=self.headers)
        logging.info("_get_request_data req: %s", str(req))
        return self._handle_request(req)

    def delete_record(self, server, zone, name, rtype):
        logging.info("delete_record entered")
        url = self._get_zone_url(server=server, name=zone)
        data = self._get_request_data(changetype='DELETE', server=server, zone=zone, name=name, rtype=rtype)
        # module.fail_json(msg=json.dumps(data))
        req = requests.patch(url=url, data=json.dumps(data), headers=self.headers)
        return self._handle_request(req)


def ensure(module, pdns_client):
    logging.info("ensure entered")
    content = module.params['content']
    disabled = module.params['disabled']
    name = module.params['name']
    rtype = module.params['type']
    ttl = module.params['ttl']
    zone_name = module.params['zone']
    logging.info("ensure initialized: %s", name)
    if zone_name not in name:
        name = '{name}.{zone}'.format(name=name, zone=zone_name)
        logging.info("ensure adding domain to name: %s", name)
    
    if not zone_name.endswith('.'):
        zone_name = zone_name + '.'
    # dumb try to fix the error message
    if not name.endswith('.'):
        name = name + '.'
    server = module.params['server']
    state = module.params['state']
    logging.info("ensure server: %s", server)
    logging.info("ensure state: %s", state)
    try:
        zone = pdns_client.get_zone(server, zone_name)
    except PowerDNSError as e:
        module.fail_json(
                msg='Could not get zone {name}: HTTP {code}: {err}'.format(name=zone_name, code=e.status_code,
                                                                           err=e.message))

    if not zone:
        logging.info("ensure zone is false")
        module.fail_json(msg='Zone not found: {name}'.format(zone=zone_name))

    # Try to find the record by name and type
    logging.info("ensure searching through records: %s", server)
    logging.info("ensure rrsets: %s", zone.get('rrsets'))
    if zone.get('rrsets'):
      record = next((item for item in zone.get('rrsets') if (item['name'] == name and item['type'] == rtype)), None)
    else:
      record = None
    # we don't get past this...
    logging.info("ensure: found record: %s", record)
    if state == 'present':
        # Create record if it does not exist
        if not record:
            try:
                pdns_client.create_record(server=server, zone=zone_name, name=name, rtype=rtype, content=content,
                                          ttl=ttl, disabled=disabled)
                return True, pdns_client.get_record(server=server, zone=zone_name, name=name)
            except PowerDNSError as e:
                module.fail_json(
                        msg='Could not create record {name}: HTTP {code}: {err}'.format(name=name, code=e.status_code,
                                                                                        err=e.message))
        # Check if changeable parameters match, else update record.
        if record.get('content', None) != content or record.get('ttl', None) != ttl:
            try:
                pdns_client.create_record(server=server, zone=zone_name, name=name, rtype=rtype, content=content,
                                          ttl=ttl, disabled=disabled)
                return True, pdns_client.get_record(server=server, zone=zone_name, name=name)
            except PowerDNSError as e:
                module.fail_json(
                        msg='Could not update record {name}: HTTP {code}: {err}'.format(name=name, code=e.status_code,
                                                                                        err=e.message))
    elif state == 'absent':
        if record:
            try:
                pdns_client.delete_record(server=server, zone=zone_name, name=name, rtype=rtype)
                return True, None
            except PowerDNSError as e:
                module.fail_json(
                        msg='Could not delete record {name}: HTTP {code}: {err}'.format(name=name, code=e.status_code,
                                                                                        err=e.message))

    return False, record

def main():
    logging.info("main entered")
    module = AnsibleModule(
            argument_spec=dict(
                    content=dict(type='str', required=False),
                    disabled=dict(type='bool', default=False),
                    name=dict(type='str', required=True),
                    server=dict(type='str', default='localhost'),
                    state=dict(type='str', default='present', choices=['present', 'absent']),
                    ttl=dict(type='int', default=86400),
                    type=dict(type='str', required=False, choices=['A', 'AAAA', 'CNAME', 'MX', 'PTR', 'SOA', 'SRV']),
                    zone=dict(type='str', required=True),
                    pdns_host=dict(type='str', default='127.0.0.1'),
                    pdns_port=dict(type='int', default=8081),
                    pdns_prot=dict(type='str', default='http', choices=['http', 'https']),
                    pdns_api_key=dict(type='str', required=False),
            ),
            supports_check_mode=True,
    )

    pdns_client = PowerDNSClient(host=module.params['pdns_host'],
                                 port=module.params['pdns_port'],
                                 prot=module.params['pdns_prot'],
                                 api_key=module.params['pdns_api_key'])

    try:
        changed, record = ensure(module, pdns_client)
        module.exit_json(changed=changed, record=record)
    except Exception as e:
        module.fail_json(msg='Error: {0}'.format(str(e)))


# import module snippets
from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()
