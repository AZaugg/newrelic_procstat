#!/usr/bin/python

import psutil
import yaml
import requests
import json
import subprocess
import logging
import signal

from socket import gethostname
from collections import namedtuple
from os import getpid
from time import sleep

# TODO: Migrate away from psutil to procfs
# TODO: Daemonise process
# TODO: Metadata metrics to newrelic
# TODO: argpaese
# TODO: Overall metrics


URL = "https://platform-api.newrelic.com/platform/v1/metrics"
GUID = "com.az.procs.procstats"

class metric(object):
    def __init__(self, t_class):

        # t_class: [CPU|VM|NET|DISK]
        # unit:    [PERCENTAGE|COUNT|...]

        self.t_class = t_class
        self.metrics = []

    def add_metric(self, unit, name, metric, namespace=None):
        named = namedtuple("datapoint", ["unit", "name", "metric", "namespace"], verbose=False)

        datapoint = named(unit=unit, name=name, metric=metric, namespace=namespace)
        self.metrics.append(datapoint)

#-----------------------------------------------------------------------------------------------------------
def sig_handle(signal, frame):
    exit(0)
#-----------------------------------------------------------------------------------------------------------
def setup_logging():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    return logger
#-----------------------------------------------------------------------------------------------------------
def run_process(logger, cmd):
    logger.debug("Running command: %s", cmd)
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)

    output = process.communicate()[0].split('\n')
    output = [line for line in output if line != '']
    logger.debug("Returned raw output of: %s", output)

    return output
#-----------------------------------------------------------------------------------------------------------
def get_cpu_stats(logger, process):

    logger.debug("Gathering CPU statistics for process %s", process)
    cpustats = metric('cpu')

    csw = process.num_ctx_switches()
    cpustats.add_metric('count', 'v_csw', csw.voluntary, 'csw')
    cpustats.add_metric('count', 'i_csw', csw.involuntary, 'csw')
    cpustats.add_metric('count', 'threads', process.num_threads())

    # Pidstat to get CPU time of process
    '''
    pidstat -p 3736
    Linux 2.6.32-504.8.1.el6.x86_64 (localhost.localdomain)     29/08/15    _x86_64_    (2 CPU)

    04:47:53          PID    %usr %system  %guest    %CPU   CPU  Command
    04:47:53         3736    0.00    0.00    0.00    0.00     1  sshd
    '''

    cmd = ["pidstat", "1", "1", "-p"]
    cmd.append(str(process.pid))

    output = run_process(logger, cmd)

    line_matrix = {}
    for line in output:
        if 'usr' in line and 'sys' in line:
            items = line.split()

            line_matrix['usr'] = items.index('%usr')
            line_matrix['sys'] = items.index('%system')

            continue

        if line != "" and line_matrix.values():
            items = line.split()

            line_matrix['usr'] = round(float(items[line_matrix['usr']]))
            line_matrix['sys'] = round(float(items[line_matrix['sys']]))

            break

    if line_matrix:
        for item in line_matrix:
            cpustats.add_metric('percentage', item, int(line_matrix[item]), 'utilization')

    return  cpustats

#-----------------------------------------------------------------------------------------------------------
def get_net_stats(logger, process):

    # TODO: bytes in/out per process /proc/<PID>/net/dev
    # TODO: errors in/out per process /proc/<PID>/net/dev

    logger.debug("Gathering Network statistics for process %s", process)
    netstats = metric('net')
    current_connections = process.connections()

    connection_types = dict()
    for connection in current_connections:
        if connection.status not in connection_types.keys():
            connection_types[connection.status] = 1
            continue

        connection_types[connection.status] += 1

    for item in connection_types:
        netstats.add_metric('count', item, connection_types[item], 'connections')

    return netstats

#-----------------------------------------------------------------------------------------------------------
def get_vm_stats(logger, process):

    logger.debug("Gathering Virtual Memory statistics for process %s", process)
    memstats = metric('mem')

    memstats.add_metric('percentage', 'percentage_usage', process.memory_percent())

    mem_info = process.memory_info_ex()
    try:
        memstats.add_metric('count', 'rss', mem_info.rss, 'usage')
        memstats.add_metric('count', 'vms', mem_info.vms, 'usage')
        memstats.add_metric('count', 'shared', mem_info.shared, 'usage')
        memstats.add_metric('count', 'text', mem_info.text, 'usage')
        memstats.add_metric('count', 'lib', mem_info.lib, 'usage')
        memstats.add_metric('count', 'data', mem_info.data, 'usage')
        memstats.add_metric('count', 'dirty', mem_info.dirtya, 'usage')
    except AttributeError:
        # Not all fields are there
        pass

    '''
    pidstat -r -p 2736
    Linux 3.13.0-29-generic (ubuntu)    31/08/15    _x86_64_    (1 CPU)

    20:23:58      UID       PID  minflt/s  majflt/s     VSZ    RSS   %MEM  Command
    20:23:58     1000      2736      0.11      0.00   22440   3720   0.74  bash
    '''

    cmd = ["pidstat", "1", "1", "-r", "-p"]
    cmd.append(str(process.pid))
    output = run_process(logger, cmd)

    line_matrix = {}
    for line in output:
        if 'minflt/s' in line and 'majflt/s' in line:
            items = line.split()

            line_matrix['minflts'] = items.index('minflt/s')
            line_matrix['majflts'] = items.index('majflt/s')

            continue

        if line != "" and line_matrix.values():
            items = line.split()

            line_matrix['minflts'] = round(float(items[line_matrix['minflts']]))
            line_matrix['majflts'] = round(float(items[line_matrix['majflts']]))

            break

    if not line_matrix:
        return memstats

    for item in line_matrix:
        memstats.add_metric('count', item, int(line_matrix[item]), 'faults')

    return memstats

#-----------------------------------------------------------------------------------------------------------
def get_io_stats(logger, process):

    # TODO: Add iostat to metrics collect
    #       rrqm/s wrqm/s r/s w/s avgrq-sz avgqu-sz await r_await w_awai

    logger.debug("Gathering IO statistics for process %s", process)
    diskstats = metric('disk')

    diskstats.add_metric('count', 'fd', process.num_fds())

    stats = process.io_counters()
    diskstats.add_metric('count', 'read', stats.read_bytes, 'bytecounters')
    diskstats.add_metric('count', 'write', stats.write_bytes, 'bytecounters')

    diskstats.add_metric('count', 'write', stats.write_count, 'iocounters')
    diskstats.add_metric('count', 'read', stats.read_count, 'iocounters')

    return diskstats

#-----------------------------------------------------------------------------------------------------------
def read_config(logger):

    # TODO: Pass in file path to config file
    logger.debug('Opening config.yml configuration file')
    try:
        with open("config.yml", 'r') as f_yaml:
            config = yaml.load(f_yaml)
    except IOError:
        logger.debug('Unable to find config.yml file')
        exit(1)

    for key in ['general', 'process']:
        if key not in config.keys():
            logger.error("%s stanza does not exist in config file", key)
            exit(1)

    processes = config['process']
    license = config['general']['license']
    duration = int(config['general']['duration'])

    if duration < 60:
        logger.warning('Duration cannot be less than 60 seconds...setting to 60')
        duraction = 60

    return processes, license, duration

#-----------------------------------------------------------------------------------------------------------
def find_pid(logger, processes):

    logger.debug('Looking up PIDs')

    pids = []

    running_procs = psutil.process_iter()

    for proc in running_procs:
        if not proc.name() in processes:
            continue

        logger.info('Watching process %s with pid %s', proc.name(), proc)
        pids.append(proc)

    return pids

#-----------------------------------------------------------------------------------------------------------
def main():
    components = []
    logger = setup_logging()
    logger.info("Starting procstat" )

    processes, license, duration = read_config(logger)
    pids = find_pid(logger, processes)

    while True:
        for pid in pids:
            collection = []
            metrics = dict()
            process = psutil.Process(pid.pid)

            collection.append(get_cpu_stats(logger, process))
            collection.append(get_net_stats(logger, process))
            collection.append(get_vm_stats(logger, process))
            collection.append(get_io_stats(logger, process))

            for metric in collection:
                for data in metric.metrics:
                    namespace = ''
                    unit = ''
                    section = metric.t_class
                    name = data.name

                    if data.namespace:
                        namespace = data.namespace + "/"

                    if data.unit:
                        unit = "[" + data.unit + "]"

                    key = "Component/%(section)s/%(namespace)s%(name)s%(unit)s" % locals()
                    value = data.metric
                    metrics[key] = value

            component_template = {
                "name": "%s-%s-%s" % (str(pid.pid), pid.name(), gethostname()),
                "guid": GUID,
                "duration": duration,
                "metrics": metrics
            }

            components.append(component_template)

        payload = {
          "agent": {
            "host" : gethostname(),
            "pid" : getpid(),
            "version" : "1.0.0"
          },
          "components": components
        }

        logger.debug("Sending payload to newrelic\n: %s", payload)

        headers = {"X-License-Key": license, "Content-Type":"application/json", "Accept":"application/json"}
        request = requests.post(url=URL, headers=headers, data=json.dumps(payload))
        logger.debug("Newrelic response code: %s", request.status_code)

        sleep(duration)

#-----------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    signal.signal(signal.SIGINT, sig_handle)
    signal.signal(signal.SIGTERM, sig_handle)
    main()
