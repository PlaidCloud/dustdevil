#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='dustdevil',
    #install_requires=['list', 'deps', 'here'],
    version="0.1.1",
    packages=find_packages(),
    author='Tartan Solutions, Inc',
    author_email='paul.morel@tartansolutions.com',
    description='Lightweight session management class for python',
    url='https://www.plaidcloud.com',
    keywords="python tornado session",
    project_urls={
        "Source Code": "https://github.com/PlaidCloud/dustdevil/tree/master",
    }
)