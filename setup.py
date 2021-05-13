#!/usr/bin/env python
from setuptools import setup, find_packages

tornado_deps = [
    'tornado'
]

postgres_deps = [
    'psycopg2-binary',
]

redis_deps = [
    'redis',
    'plaidcloud-config==0.1.8',
]

memcached_deps = [
    'pylibmc'
]

mongo_deps = [
    'pymongo'
]

all_deps = tornado_deps + postgres_deps + redis_deps + memcached_deps + mongo_deps
# test_deps = all_deps + [ ## only tests for redis so far
test_deps = redis_deps + [
    'pytest',
    'pytest-cov',
    'pytest-runner',
]

extras = {
    'test': test_deps,
    'tornado': tornado_deps,
    'postgres': postgres_deps,
    'redis': redis_deps,
    'memcached': memcached_deps,
    'mongo': mongo_deps
}

setup(
    name='dustdevil',
    version="0.1.1",
    packages=find_packages(),
    author='Tartan Solutions, Inc',
    author_email='paul.morel@tartansolutions.com',
    description='Lightweight session management class for python',
    url='https://www.plaidcloud.com',
    keywords="python tornado session",
    project_urls={
        "Source Code": "https://github.com/PlaidCloud/dustdevil/tree/master",
    },
    tests_require=test_deps,
    setup_requires=['pytest-runner'],
    extras_require=extras,
)
