#!/usr/bin/env python

import maas_common
import subprocess
import re


def recon_output(for_ring, options=None):
    """Run swift-recon and filter out extraneous printed lines.

    ::

        >>> recon_output('account', '-r')
        ['[2014-11-21 00:25:16] Checking on replication',
         '[replication_failure] low: 0, high: 0, avg: 0.0, total: 0, Failed: 0.0%, no_result: 0, reported: 2',
         '[replication_success] low: 2, high: 4, avg: 3.0, total: 6, Failed: 0.0%, no_result: 0, reported: 2',
         '[replication_time] low: 0, high: 0, avg: 0.0, total: 0, Failed: 0.0%, no_result: 0, reported: 2',
         '[replication_attempted] low: 1, high: 2, avg: 1.5, total: 3, Failed: 0.0%, no_result: 0, reported: 2',
         'Oldest completion was 2014-11-21 00:24:51 (25 seconds ago) by 192.168.31.1:6002.',
         'Most recent completion was 2014-11-21 00:24:56 (20 seconds ago) by 192.168.31.2:6002.']

    :param str for_ring: Which ring to run swift-recon on
    :param list options: Command line options with which to run swift-recon
    :returns: Strings from output that are most important
    :rtype: list
    """
    command = ['swift-recon', for_ring]
    command.extend(options or [])
    out = subprocess.check_output(command)
    return filter(lambda s: s and not s.startswith(('==', '-')),
                  out.split('\n'))


def swift_replication(for_ring):
    """Parse swift-recon's replication statistics and return them.

    ::

        >>> swift_replication('account')
        {'attempted': {'avg': '1.5',
                       'failed': '0.0%',
                       'high': '2',
                       'low': '1',
                       'total': '3'},
         'failure': {'avg': '0.0',
                     'failed': '0.0%',
                     'high': '0',
                     'low': '0',
                     'total': '0'},
         'success': {'avg': '3.0',
                     'failed': '0.0%',
                     'high': '4',
                     'low': '2',
                     'total': '6'},
         'time': {'avg': '0.0',
                  'failed': '0.0%',
                  'high': '0',
                  'low': '0',
                  'total': '0'}}

    :param str for_ring: Which ring to run swift-recon on
    :returns: Dictionary of attempted, failed, success, and time statistics
    :rtype: dict
    """
    regexp = re.compile('\[replication_(?P<replication_type>\w+)\]\s+'
                        'low:\s+(?P<low>\d+),\s+high:\s+(?P<high>\d+)'
                        ',\s+avg:\s+(?P<avg>\d+.\d+),\s+total:\s+'
                        '(?P<total>\d+),\s+Failed:\s+(?P<failed>\d+.\d+%)')
    replication_dicts = map(lambda l: regexp.match(l).groupdict(),
                            filter(lambda s: s.startswith('[replication_'),
                                   recon_output(for_ring, ['-r'])))

    # reduce could work here but would require an enclosed function which is
    # less readable than this loop
    replication_statistics = {}
    for rep_dict in replication_dicts:
        replication_statistics[rep_dict.pop('replication_type')] = rep_dict

    return replication_statistics
