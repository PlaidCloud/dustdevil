#!/usr/bin/env python

from distutils.core import setup
from dustdevil.handler import __version__

setup(
    name='dustdevil',
    version=__version__,
    description='Lightweight session management class for python',
    author='Tartan Solutions, Inc',
    url='https://www.plaidcloud.com',
    packages=['dustdevil']
)