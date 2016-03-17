newrelic_procstat:
==================

A Newrelic plugin to send detailed processes statistics to newrelic at a per process level.  Allowing you to gain a detailedinsight into process footprint on a server. This plugin allows you to collect detailed metrics of processes and forward them onto Newrelic, at present the plugin collects the following metrics at a per process level:
   - Disk
    - Megabytes read from block device
    - Megabytes written to block device
   - VM
    - Memory used
    - Major faults
    - Minor faults
    - break down of memory usage
   - CPU
    - voluntary context swtich count
    - involuntary context switch count
    - thread count
    - usr time
    - sys time
   - Network
    - Network states

Still To DO:
============
- Write init script
- Package script (add it to pypi)
- Add argument parse:
  - to accept config file
  - Set logging level

Requirements:
=============
Plugin requires the following packages

   Python package:
   - python 2.7 >
   - requests
   - psutil
   - PyYAML



   Linux packages:
   - systat
   - python-devel
   - GCC

 Once we remove the reliance on python package psutil we will no longer need gcc and python-devel


Installation:
=============
- Clone repo
- Edit config.yml file and add your process names you want to watch
```
 $ git clone https://github.com/AZaugg/newrelic_procstat.git
 $ nohup python newrelic_procstat/procstat.py &
```

Configuration:
==============
Edit the config.yml file and add the name of the process you want to monitor

Run it:
=======
nohup python procstat.py &

Temporary fix while I daemonize the process


Contributing:
=============
Pull requests are welcome. A few bits and bobs to make it a completely shippable package
