#!/usr/bin/env python

# Copyright 2017, Rackspace US, Inc.
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

import argparse

import ipaddr
from maas_common import get_auth_ref
from maas_common import get_magnum_client
from maas_common import metric_bool
from maas_common import print_output
from maas_common import status_err
from maas_common import status_ok
from magnumclient.common.apiclient import exceptions as exc


def check(auth_ref, args):
    MAGNUM_ENDPOINT = 'http://{ip}:9511/v1'.format(ip=args.ip,)

    try:
        if args.ip:
            magnum = get_magnum_client(endpoint=MAGNUM_ENDPOINT)
        else:
            magnum = get_magnum_client()

        api_is_up = True
    except exc.HttpError as e:
        api_is_up = False
    # Any other exception presumably isn't an API error
    except Exception as e:
        status_err(str(e))
    else:
        services = magnum.mservices.list()

    status_ok()
    metric_bool('magnum_api_local_status', api_is_up)
    if api_is_up:
        for service in services:
            metric_bool('_'.join([service.binary, 'status']),
                        True if service.state == 'up' else False)


def main(args):
    auth_ref = get_auth_ref()
    check(auth_ref, args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Check Magnum API against local or remote address')
    parser.add_argument('ip', nargs='?', type=ipaddr.IPv4Address,
                        help="Check Magnum API against "
                        " local or remote address")
    parser.add_argument('--telegraf-output',
                        action='store_true',
                        default=False,
                        help='Set the output format to telegraf')
    args = parser.parse_args()
    with print_output(print_telegraf=args.telegraf_output):
        main(args)
