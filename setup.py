#!/usr/bin/env python
from distutils.core import setup

setup(
    name='newrelic_procstat',
    version='0.1.0',
    description='Send detailed process metrics to newrelic',
    author='andy.zaugg',
    author_email='andy.zaugg@gmail.com',
    url='https://github.com/AZaugg/newrelic_procstat',
    packages=['newrelic_procstat'],
    long_description="Send detailed metrics of a specific process to newrelic, capturing process stats on a per process level",
    entry_points={'console_scripts': ['newrelic_procstat.procstat.main']}
)