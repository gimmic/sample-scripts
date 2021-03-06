#!/usr/bin/env python
# Big Monitoring Fabric Out-of-band config script 
import requests
import json 
import sys

requests.packages.urllib3.disable_warnings()

class Controller(object):
    """

    controller version 5.x

    """
    def __init__(self, controller_ip, username, password):
        self.cookie = ""
        self.bigtap_path = '/api/v1/data/controller/applications/bigtap/'
        self.controller_path = '/api/v1/data/controller/core/'
        self.username = username
        self.password = password
        self.controller_ip = controller_ip
        self.get_cookie()

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.release_cookie()

    def controller_request(self, method, path, data="", dry_run=False):
        if not self.controller_ip:
            print 'You must set controller_ip to the IP address of your controller'
        controller_url = "https://%s:443" % self.controller_ip
        # append path to the controller url, e.g. "https://192.168.23.98:8443" + "/api/v1/auth/login"
        url = controller_url + path
        # if a cookie exists then use it in the header, otherwise create a header without a cookie
        if self.cookie:
            session_cookie = 'session_cookie=%s' % self.cookie
            headers = {"content-type": "application/json", 'Cookie': session_cookie}
        else:
            headers = {"content-type": "application/json"}
        if dry_run:
            print 'METHOD ', method, ' URL ', url, ' DATA ', data, ' HEADERS ', headers
            return None
        else:
            # submit the request 
            response = requests.request(method, url, data=data, headers=headers, verify=False)
            # if content exists then return it, otherwise return the HTTP status code
            if response.content:
                return json.loads(response.content)
            else:
                return response.status_code
                        
    def make_request(self, verb, path, data):
        result = self.controller_request(verb, path, data=data)
        if result == 200:
            return True
        print result
        sys.exit(1)

    def get_cookie(self):
        method = 'POST'
        path = "/auth/login"
        data = '{"user":"%s", "password":"%s"}' % (self.username, self.password)
        json_content = self.controller_request(method, path, data)
        self.cookie = json_content['session_cookie']
        print 'Login to %s successful' % self.controller_ip

    def release_cookie(self):
        method = "DELETE"
        path = '/api/v1/data/controller/core/aaa/session[auth-token="%s"]' % self.cookie
        status_code = self.controller_request(method, path)
        if status_code == 200:
            print 'Logout successful'

    def get_controller_version(self):
        method = 'GET'
        path = '/rest/v1/system/version'
        data = '{}'
        json_content = self.controller_request(method, path, data=data, dry_run=True)
        return json_content[0] if type(json_content) == list else None

    def configure_bigtap_interface_role(self, switch_dpid, interface, name, role):
        path = self.bigtap_path+ 'interface-config[interface="%s"][switch="%s"]' % (interface, switch_dpid)
        data = '{"interface": "%s", "switch": "%s", "role": "%s", "name": "%s"}' % (interface, switch_dpid, role, name)
        self.make_request('PUT', path, data=data)

    def add_policy(self, specs):
        try:
            name = specs['name']
            action = specs['action']
            priority = specs['priority']
            duration = specs['duration']
            start_time = specs['start_time']
            delivery_packet_count = specs['delivery_packet_count']
            interfaces = specs['interfaces']
            rules = specs['rules']
        except KeyError, e:
            print "policy specs error %s" % str(e)
            sys.exit(1)

        path = self.bigtap_path+ 'view[name="admin-view"]/policy[name="%s"]' % name
        data = '{"name": "%s"}' % name
        self.make_request('PUT', path, data)

        path = self.bigtap_path+ 'view[name="admin-view"]/policy[name="%s"]' % name
        data = '{"action": "%s"}' % action
        self.make_request('PATCH', path, data)
    
        path = self.bigtap_path+ 'view[name="admin-view"]/policy[name="%s"]' % name
        data = '{"priority": %s}' % priority
        self.make_request('PATCH', path, data)

        duration = 0
        delivery_packet_count = 0
        path = self.bigtap_path+ 'view[name="admin-view"]/policy[name="%s"]' % name
        data = '{"duration": %s, "start-time": %s, "delivery-packet-count": %s}' % (duration, start_time, delivery_packet_count)
        self.make_request('PATCH', path, data)

        index = 5
        for interface in interfaces:
            role = interfaces[interface]
            path = self.bigtap_path+ 'view[name="admin-view"]/policy[name="%s"]/%s-group[name="%s"]' % (name, role, interface)
            data = '{"name": "%s"}'  % interface
            self.make_request('PUT', path, data)
            index += 1

        for rule in rules:
            path = self.bigtap_path+ 'view[name="admin-view"]/policy[name="%s"]/rule[sequence=%s]' % (name, rule['sequence'])
            data = json.dumps(rule)
            self.make_request('PUT', path, data)
            index += 1

    def create_tunnel(self, specs, dry_run=False):
        try:
            switch_dpid = specs['switch_dpid']
            tunnel_name = specs['tunnel_name']
            destination_ip = specs['destination_ip']
            source_ip = specs['source_ip']
            mask = specs['mask']
            gateway_ip = specs['gateway_ip']
            tunnel_src_ip = specs['destination_ip']
            vpn_key = specs['vpn_key']
            encap_type = specs['encap_type']
            interface = specs['interface']
            direction = specs['direction']
            loopback_interface = ''
            if direction == 'bidirectional' or direction == 'transmit-only':
                loopback_interface = specs['loopback_interface']
        except KeyError, e:
            print "tunnel specs error %s" % str(e)
            sys.exit(1)

        path = self.controller_path+ 'switch[dpid="%s"]/interface[name="%s"]' % (switch_dpid, tunnel_name)
        data = '{"name": "%s"}' % tunnel_name
        self.make_request('PUT', path, data)

        path = self.controller_path+ 'switch[dpid="%s"]/interface[name="%s"]/ip-config' % (switch_dpid, tunnel_name)
        data = '{"destination-ip": "%s"}' % destination_ip
        self.make_request('PUT', path, data)
        
        path = self.controller_path+ 'switch[dpid="%s"]/interface[name="%s"]' % (switch_dpid, tunnel_name)
        data = '{"vpn-key": %s, "encap-type": "%s"}' % (vpn_key, encap_type)
        self.make_request('PATCH', path, data)

        path = self.controller_path+ 'switch[dpid="%s"]/interface[name="%s"]' % (switch_dpid, tunnel_name)
        data = '{"parent-interface": "%s"}' % interface
        self.make_request('PATCH', path, data)

        path = self.controller_path+ 'switch[dpid="%s"]/interface[name="%s"]' % (switch_dpid, tunnel_name)
        data = '{"direction": "%s", "loopback-interface": "%s", "type": "tunnel"}' % (direction, loopback_interface)
        self.make_request('PATCH', path, data)

        path = self.controller_path+ 'switch[dpid="%s"]/interface[name="%s"]/ip-config' % (switch_dpid, tunnel_name)
        data = '{"source-ip": "%s", "ip-mask": "%s", "gateway-ip": "%s"}' % (source_ip, mask, gateway_ip)
        self.make_request('PATCH', path, data)

    def create_ip_address_set(self, name, ip_type, dry_run=False):
        path = self.bigtap_path+ 'ip-address-set[name="%s"]' % name
        data = '{"name": "%s"}' % name
        self.make_request('PUT', path, data)

        path = self.bigtap_path+ 'ip-address-set[name="%s"]' % name
        data = '{"ip-address-type": "%s"}' % ip_type
        self.make_request('PATCH', path, data)

    def add_ip_to_group(self, name, ip, mask, dry_run=False):
        path = self.bigtap_path+ 'ip-address-set[name="%s"]/address-mask-set[ip="%s"][ip-mask="%s"]' % (name, ip, mask)
        data = '{"ip": "%s", "ip-mask": "%s"}' % (ip, mask)
        self.make_request('PUT', path, data)

    def delete_ip_from_group(self, name, ip, mask, dry_run=False):
        path = self.bigtap_path+ 'ip-address-set[name="%s"]/address-mask-set[ip="%s"][ip-mask="%s"]' % (name, ip, mask)
        data = '{}'
        self.make_request('DELETE', path, data)
