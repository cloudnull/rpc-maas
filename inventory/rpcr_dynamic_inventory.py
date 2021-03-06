#!/usr/bin/env python
# need to maake this file executable
# Copyright 2018, Rackspace US, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import copy
import json
import getopt
import os
import re
import socket
import sys

from heatclient import client as heat_client
from tripleo_common.inventory import TripleoInventory
from tripleo_validations.utils import get_auth_session

from base_inventory import MaasInventory
from rpcr_tripleo_host_group_mapping import TRIPLEO_MAPPING_GROUP


def validate_ip(s):
    try:
        socket.inet_pton(socket.AF_INET, s)
        return True
    except socket.error:
        return False


class RPCRMaasInventory(MaasInventory):

    def __init__(self):
        # Load stackrc environment variable file
        self.load_stackrc_file()
        self.load_os_cacert()
        super(RPCRMaasInventory, self).__init__()

    def read_input_inventory(self):
        auth_url = os.environ.get('OS_AUTH_URL')
        os_username = os.environ.get('OS_USERNAME')
        os_project_name = os.environ.get(
            'OS_PROJECT_NAME', os.environ.get('OS_TENANT_NAME'))
        os_password = os.environ.get('OS_PASSWORD')
        os_auth_token = os.environ.get('OS_AUTH_TOKEN')
        os_cacert = os.environ.get('OS_CACERT')
        ansible_ssh_user = os.environ.get('ANSIBLE_SSH_USER', 'heat-admin')
        self.plan_name = (os.environ.get('TRIPLEO_PLAN_NAME') or
                          os.environ.get('STACK_NAME_NAME') or
                          self.get_tripleo_plan_name())
        session = get_auth_session(auth_url,
                                   os_username,
                                   os_project_name,
                                   os_password,
                                   os_auth_token,
                                   os_cacert)
        hclient = heat_client.Client('1', session=session)
        inventory = TripleoInventory(
            session=session,
            hclient=hclient,
            auth_url=auth_url,
            cacert=os_cacert,
            project_name=os_project_name,
            username=os_username,
            ansible_ssh_user=ansible_ssh_user,
            plan_name=self.plan_name)
        return inventory.list()

    def load_stackrc_file(self):
        undercloud_env_file_path = '/home/stack/stackrc'
        if not os.path.exists(undercloud_env_file_path):
            raise RuntimeError('No undercloud stackrc file found, aborting...')
        envre = re.compile(
            '^(?:export\s)?(?P<key>\w+)(?:\s+)?=(?:\s+)?(?P<value>.*)$'
        )
        with open(undercloud_env_file_path) as ins:
            for line in ins:
                match = envre.match(line)
                if match is None:
                    continue
                k = match.group('key')
                v = match.group('value').strip('"').strip("'")
                os.environ[k] = v

    def load_os_cacert(self):
        os_cert_path = '/etc/pki/ca-trust/source/anchors/'
        if os.path.exists(os_cert_path):
            # load the cert file in this directory
            certs = []
            for f in os.listdir(os_cert_path):
                f_path = os.path.join(os_cert_path, f)
                if os.path.isfile(f_path):
                    certs.append(f_path)
            os.environ['OS_CACERT'] = ' '.join(certs)

    def get_tripleo_plan_name(self):
        oss_command = 'stack list -f json'
        stack_list_result = self.run_oss_command(oss_command)
        self.plan_name = (
            json.loads(stack_list_result.getvalue())[0]['Stack Name']
        )
        return self.plan_name

    def add_all_group_hosts(self, group_name, input_inventory):
        """Given a group name in input_inventory), recursively add it
        child group and child host
        """
        if 'hosts' in input_inventory[group_name]:
            self.inventory[group_name] = copy.deepcopy(
                input_inventory[group_name]
            )
            # questions: would we have more than one hosts per leaf
            # group ? if so, what is the ansible_host value there?
            # If ansible_host already exists in group vars or host vars
            # do not assign it at host group level
            try:
                if 'ansible_host' not in input_inventory[group_name]['vars']:
                    if validate_ip(input_inventory[group_name]['hosts'][0]):
                        self.inventory[group_name]['vars']['ansible_host'] = (
                            input_inventory[group_name]['hosts'][0])
            except IndexError:
                print("Oops, I didn't find that host.")
                quit()
            # We want undercloud's name hostname to be director
            if group_name.lower() == 'undercloud':
                self.inventory[group_name]['hosts'] = [os.getenv(
                    'MAAS_DIRECTOR_NAME',
                    'director'
                )]
            else:
                if len(self.inventory[group_name]['hosts']) == 1 and \
                        validate_ip(input_inventory[group_name]['hosts'][0]):
                    self.inventory[group_name]['hosts'] = [group_name]
        else:
            self.inventory[group_name] = copy.deepcopy(
                input_inventory[group_name]
            )
            for child in input_inventory[group_name]['children']:
                self.add_all_group_hosts(child, input_inventory)

    def generate_env_specific_variables(self):
        oss_command = ('stack resource show {plan} '
                       'EndpointMap -c attributes -f json').format(
                           plan=self.plan_name)

        endpoint_map_result = self.run_oss_command(oss_command)
        self.endpoint_map_result_json = json.loads(
            endpoint_map_result.getvalue().strip().rstrip('0'))

        # get MysqlRootPassword
        oss_command = ('stack resource show {plan} '
                       'MysqlRootPassword -c attributes -f json').format(
                           plan=self.plan_name)
        password_result = self.run_oss_command(oss_command)
        self.password_result_json = json.loads(password_result.getvalue().
                                               strip().rstrip('0'))

    def do_host_group_mapping(self, input_inventory):
        for source_group, children_list in TRIPLEO_MAPPING_GROUP.items():
            for child in children_list:
                if (child not in self.inventory and child in input_inventory):
                    self.add_all_group_hosts(child, input_inventory)

            self.inventory[source_group] = {
                'children': children_list
            }

    def generate_inventory(self):
        input_inventory = self.read_input_inventory()
        # generate some product specific variables
        self.generate_env_specific_variables()
        self.inventory['_meta'] = copy.deepcopy(input_inventory['_meta'])
        for host in self.inventory['_meta']['hostvars']:
            self.inventory['_meta']['hostvars'][host]['ansible_user'] = (
                'heat-admin')
            (self.inventory['_meta']['hostvars'][host]['ansible_become']) = (
                'yes'
            )
            (self.inventory['_meta']['hostvars'][host]
                ['ansible_ssh_private_key_file']) = (
                    '/home/stack/.ssh/id_rsa'
            )
            (self.inventory['_meta']['hostvars'][host]
                ['galera_root_password']) = (
                    self.password_result_json['attributes']['value']
            )

            (self.inventory['_meta']['hostvars'][host]
                ['internal_lb_vip_address']) = (
                self.endpoint_map_result_json['attributes']
                ['endpoint_map']['KeystoneInternal']['host']
            )
            (self.inventory['_meta']['hostvars'][host]
                ['external_lb_vip_address']) = (
                self.endpoint_map_result_json['attributes']
                ['endpoint_map']['KeystonePublic']['host']
            )
            (self.inventory['_meta']['hostvars'][host]['maas_stackrc']) = (
                '/home/stack/{plan_name}rc'.format(plan_name=self.plan_name)
            )
        self.do_host_group_mapping(input_inventory)


def main():
    usage = "USAGE: rpcr_dynamic_inventory.py\n" \
            "--list <list>\n" \
            "--host <host>\n"
    try:
        opts, args = getopt.getopt(sys.argv[1:], "list:host", ["list", "host"])
    except getopt.GetoptError:
        print(usage)
        sys.exit(2)


# Get the inventory.
if __name__ == "__main__":
    RPCRMaasInventory()
