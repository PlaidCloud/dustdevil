#!/usr/bin/env python

from dustdevil import session

try:
    from tornado import database
except ImportError:
    pass

try:
    import psycopg2
except ImportError:
    pass

try:
    import redis
    from redis.sentinel import Sentinel
except ImportError:
    pass

__author__ = "Paul Morel"
__copyright__ = "Copyright 2019 Tartan Solutions, Inc"
__credits__ = ["Paul Morel", "Brian McFadden", "Garrett Bates"]
__license__ = "Apache 2.0"
__version__ = "1.1.0"
__maintainer__ = "Paul Morel"
__email__ = "paul.morel@tartansolutions.com"
__status__ = "Alpha"


class Handler(object):

    """Dust Devil Main Session Handling Class"""

    def __init__(self, settings):

        # logger = plogging.get_logger_adapter(__name__, None, None)
        self.__kw = {'security_model': settings.get('session_security_model', []),
                     'duration': settings.get('duration', 900),
                     'regeneration_interval': settings.get('session_regeneration_interval', 240),
                     'catalog': settings.get('session_catalog', 'tornado_sessions'),
                     'cookie_name': settings.get('session_cookie_name', 'session_id'),
                     'field_store': settings.get('session_field_store')
                     }
        url = settings.get('session_storage', '')

        if url.startswith('mysql'):
            self.storage_class = session.MySQLSession

            u, p, host, d, port = self.storage_class._parse_connection_details(url)

            h = "{0}:{1}".format(host, port)

            self.storage_client = database.Connection(h, d, user=u, password=p)

            if not self.storage_client.get("""show tables like 'tornado_sessions'"""):
                self.storage_client.execute(  # create table if it doesn't exist
                    """create table tornado_sessions (
                    session_id varchar(64) not null primary key,
                    data longtext,
                    expires integer,
                    ip_address varchar(46),
                    user_agent varchar(255)
                    );""")

        elif url.startswith('postgresql'):
            self.storage_class = session.PostgresSession

            u, p, host, d, port = self.storage_class._parse_connection_details(url)
            # print "User: {0}".format(u)
            # print "Host {0}".format(host)
            # print "Database {0}".format(d)

            self.storage_client = psycopg2.connect(host=host, port=port, database=d, user=u, password=p)

        elif url.startswith('sqlite'):
            raise NotImplementedError
        elif url.startswith('memcached'):
            self.storage_class = session.MemcachedSession
            self.storage_client = None  # TODO - Figure out how to open a memcached session
        elif url.startswith('mongodb'):
            self.storage_class = session.MongoDBSession
            self.storage_client = None  # TODO - Figure out how to open a mongodb session
        elif url.startswith('redis'):
            self.storage_class = session.RedisSession
            groupname, p, host, d, port = self.storage_class._parse_connection_details(url)
            if (groupname):
                sentinel = redis.sentinel.Sentinel([(host, port)], socket_timeout=0.1)
                self.storage_client = sentinel.master_for(groupname)
            else:
                self.storage_client = redis.Redis(host=host, port=port, db=d, password=p)
        elif url.startswith('dir'):
            self.storage_class = session.DirSession
            self.storage_client = url[6:]
        elif url.startswith('file'):
            self.storage_class = session.FileSession
            self.storage_client = url[7:]
        else:
            return None

    def create_session(self, tornado_web, session_id=None):
        """Creates a session handler connection to the persistent storage container
        Current support for: MySQL, Memcached, MongoDB, Redis, Directory, and File sessions"""
        # settings = self.application.settings # just a shortcut

        # logger = plogging.get_logger_adapter(__name__, None, None)

        new_session = None
        old_session = None

        session_id = session_id or tornado_web.get_secure_cookie(self.__kw['cookie_name'])
        ip_address = tornado_web.request.remote_ip
        user_agent = tornado_web.request.headers.get('User-Agent')

        kw = {'security_model': self.__kw['security_model'],
              'duration': self.__kw['duration'],
              'ip_address': ip_address,
              'user_agent': user_agent,
              'tornado_web': tornado_web,
              'regeneration_interval': self.__kw['regeneration_interval'],
              'catalog': self.__kw['catalog'],
              'cookie_name': self.__kw['cookie_name'],
              'field_store': self.__kw['field_store']
              }

        old_session = self.storage_class.load(session_id, self.storage_client, **kw)

        if old_session is None or old_session._is_expired():  # create a new session
            new_session = self.storage_class(self.storage_client, **kw)

        if old_session is not None:
            if old_session._should_regenerate():
                old_session.refresh(new_session_id=True)
            return old_session

        return new_session
