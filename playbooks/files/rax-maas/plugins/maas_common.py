#!/usr/bin/env python

# Copyright 2014, Rackspace US, Inc.
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

import urlparse

from monitorstack import utils
from monitorstack.utils import os_utils as ost

import monitorstack_creds

from maas_metric_common import *


class Struct(object):
    def __init__(self, items):
        self.__dict__.update(items)


class OSClient(object):
    def __init__(self):
        pass

    @property
    def ost_conn(self):
        creds = utils.read_config('/root/monitorstack.ini')['ALL']
        return ost.OpenStack(os_auth_args=creds)

    def _session_req(self, endpoint_url, path):
        """Return compute resource limits for a project.

        :param path: URL path to make a request against.
        :type path: str
        :param interface: Interface name, normally [internal, public, admin].
        :type interface: str
        :returns: dict
        """
        if not endpoint_url.endswith('/'):
            endpoint_url = '%s/' % endpoint_url
        sess_url = urlparse.urljoin(endpoint_url, path)
        return self.ost_conn.conn.session.get(sess_url).json()

    def _glance_list_images(self, endpoint=None):
        """Return a list images."""
        if endpoint:
            sess_items = self._session_req(
                endpoint_url=endpoint,
                path='images'
            )
            items = list()
            for item in sess_items['images']:
                items.append(
                    self.ost_conn.conn.image.get_image(item['id'])
                )
            return items
        else:
            return self.ost_conn.conn.image.images()

    def glance_shim(self, endpoint=None):
        """Return a pusedo glance client object.

        The glance shim is a nested set of classes which fake the old client
        syntax.
        """
        class glance(object):
            class images(object):
                @staticmethod
                def list(search_opts=None):
                    items = list()
                    for item in self._glance_list_images(endpoint):
                        items.append(item)
                    return items
        return glance

    def _heat_list_stacks(self, endpoint=None):
        """Return a list of stacks."""
        if endpoint:
            tenant_id = self.ost_conn.conn.session.get_user_id()
            sess_items = self._session_req(
                endpoint_url=endpoint,
                path='%s/stacks' % tenant_id
            )
            items = list()
            for item in sess_items['stacks']:
                items.append(Struct(item))
            return items
        else:
            return self.ost_conn.conn.orchestration.stacks()

    def heat_shim(self, endpoint=None):
        """Return a pusedo heat client object.

        The heat shim is a nested set of classes which fake the old client
        syntax.
        """
        class heat(object):
            class build_info(object):
                @staticmethod
                def build_info():
                    items = list()
                    for item in self._heat_list_stacks(endpoint):
                        items.append(item)
                    return items
        return heat

    def _ironic_list_nodes(self, endpoint=None):
        """Return a list of nodes."""
        if endpoint:
            sess_items = self._session_req(
                endpoint_url=endpoint,
                path='nodes'
            )
            items = list()
            for item in sess_items['nodes']:
                items.append(Struct(item))
            return items
        else:
            return self.ost_conn.conn.bare_metal.nodes()

    def ironic_shim(self, endpoint=None):
        """Return a pusedo ironic client object.

        The heat shim is a nested set of classes which fake the old client
        syntax.
        """
        class ironic(object):
            class node(object):
                @staticmethod
                def list():
                    items = list()
                    for item in self._ironic_list_nodes(endpoint):
                        items.append(item)
                    return items
        return ironic

    def _magnum_list(self, endpoint=None, list_type=None):
        """Return a list of nodes."""
        if endpoint:
            sess_items = self._session_req(
                endpoint_url='http://%s:9511/v1' % endpoint,
                path='v1/%s' % list_type
            )
        else:
            identity = self.ost_conn.conn.identity
            services = identity.services()
            endpoints = identity.endpoints()
            for service in services:
                if service.type.lower() == 'container-infra':
                    for endpoint in endpoints:
                        if endpoint.service_id == service.id:
                            if endpoint.interface.lower() == 'internal':
                                endpoint_data = identity.get_endpoint(endpoint)
                                sess_items = self._session_req(
                                    endpoint_url=endpoint_data.url,
                                    path='v1/%s' % list_type
                                )
            else:
                raise SystemExit('No magnum endpoint found.')

        items = list()
        for item in items['nodes']:
            items.append(Struct(item))
        return items

    def magnum_shim(self, endpoint=None):
        """Return a pusedo magnum client object.

        The heat shim is a nested set of classes which fake the old client
        syntax.
        """
        class magnum(object):
            class cluster_templates(object):
                @staticmethod
                def list():
                    items = list()
                    for item in self._magnum_list(endpoint,
                                                  list_type='mservices'):
                        items.append(item)
                    return items
            class mservices(object):
                @staticmethod
                def list():
                    items = list()
                    for item in self._magnum_list(endpoint,
                                                  list_type='clustertemplates'):
                        items.append(item)
                    return items
        return ironic

    def _neutron_list_agents(self, endpoint, list_type=None):
        """Return a list of nodes."""
        if endpoint:
            sess_items = self._session_req(
                endpoint_url=endpoint,
                path='v2.0/agents'
            )
            items = list()
            for item in sess_items['agents']:
                items.append(Struct(item))
            return items
        else:
            return self.ost_conn.conn.network.agents()

    def _neutron_list_networks(self, endpoint):
        """Return a list of nodes."""
        if endpoint:
            sess_items = self._session_req(
                endpoint_url=endpoint,
                path='v2.0/networks'
            )
            items = list()
            for item in sess_items['networks']:
                items.append(Struct(item))
            return items
        else:
            return self.ost_conn.conn.network.networks()

    def _neutron_list_routers(self, endpoint):
        """Return a list of nodes."""
        if endpoint:
            sess_items = self._session_req(
                endpoint_url=endpoint,
                path='v2.0/routers'
            )
            items = list()
            for item in sess_items['routers']:
                items.append(Struct(item))
            return items
        else:
            return self.ost_conn.conn.network.routers()

    def _neutron_list_subnets(self, endpoint):
        """Return a list of nodes."""
        if endpoint:
            sess_items = self._session_req(
                endpoint_url=endpoint,
                path='v2.0/subnets'
            )
            print(sess_items)
            items = list()
            for item in sess_items['subnets']:
                items.append(Struct(item))
            return items
        else:
            return self.ost_conn.conn.network.subnets()

    def neutron_shim(self, endpoint=None):
        """Return a pusedo neutron client object.

        The heat shim is a nested set of classes which fake the old client
        syntax.
        """
        class neutron(object):
            @staticmethod
            def list_agents(host=None):
                return {'agents': list(self._neutron_list_agents(endpoint))}
            @staticmethod
            def list_networks():
                return {'networks': list(self._neutron_list_networks(endpoint))}
            @staticmethod
            def list_routers():
                return {'routers': list(self._neutron_list_routers(endpoint))}
            @staticmethod
            def list_subnets():
                return {'subnets': list(self._neutron_list_subnets(endpoint))}
        return neutron


def get_auth_details():
    """Return a dict of authentication credentials."""
    return monitorstack_creds.get_auth_details()


def get_auth_ref():
    """Return an authentication object in dict form."""
    _ref = get_keystone_client()
    auth_ref = dict()
    auth_ref['auth_token'] = _ref.auth_token
    auth_ref['expires_at'] = _ref.expires
    auth_ref['version'] = _ref.version
    return auth_ref


def get_endpoint_url_for_service(service_type, auth_ref, interface):
    """Return the endpoint URL for a given service.

    NOTE(cloudnull): The "auth_ref" key is only here for legacy purposes. This
                     should be removed when the octavia plugins can be updated.
    """
    return self.conn.session.get_endpoint(
        interface=interface,
        service_type=service_type
    )

def get_glance_client(endpoint=None):
    """Return a psuedo client objcet."""
    _ost = OSClient()
    return _ost.glance_shim(endpoint=endpoint)


def get_heat_client(endpoint=None):
    """Return a psuedo client objcet."""
    _ost = OSClient()
    return _ost.heat_shim(endpoint=endpoint)


def get_ironic_client(endpoint=None):
    """Return a psuedo client objcet."""
    _ost = OSClient()
    return _ost.ironic_shim(endpoint=endpoint)


def get_keystone_client(auth_ref=None):
    """Return a keystone object.

    NOTE(cloudnull): The "auth_ref" key is only here for legacy purposes. This
                     should be removed when the octavia plugins can be updated.
    """
    _ost = OSClient()
    return _ost.ost_conn.conn.authenticator.get_auth_ref(
        session=_ost.ost_conn.conn.session
    )


def get_magnum_client(endpoint=None):
    """Return a psuedo client objcet."""
    _ost = OSClient()
    return _ost.ironic_shim(endpoint=endpoint)


def get_neutron_client(endpoint_url=None):
    """Return a psuedo client objcet.

    NOTE(cloudnull): The "endpoint_url" key is different for legacy purposes.
                     This should be set to "endpoint" when the neutron plugins
                     can be updated.
    """
    _ost = OSClient()
    return _ost.neutron_shim(endpoint=endpoint_url)


def get_nova_client():
    pass
