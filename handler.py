#!/usr/bin/env python

import session
from tornado import database

__author__ = "Paul Morel"
__copyright__ = "Copyright 2010 Tartan Solutions, Inc"
__credits__ = ["Paul Morel", "Brian McFadden"]
__license__ = "Apache 2.0"
__version__ = "1.0"
__maintainer__ = "Paul Morel"
__email__ = "paul.morel@tartansolutions.com"
__status__ = "Alpha"

class Handler(object):
    """Dust Devil Main Session Handling Class"""
    
    def __init__(self, settings):
        
        self.__kw = {'security_model': settings.get('session_security_model', []),
              'duration': settings.get('session_age', 900),
              'regeneration_interval': settings.get('session_regeneration_interval', 240),
              'catalog': settings.get('session_catalog','tornado_sessions'),
              'cookie_name': settings.get('session_cookie_name', 'session_id')
              }
        url = settings.get('session_storage','')
        
        if url.startswith('mysql'):
            self.__container = session.MySQLSession
            
            u, p, h, d = self.__container._parse_connection_details(url)
            self.__database = database.Connection(h, d, user=u, password=p)
            
            if not self.__database.get("""show tables like 'tornado_sessions'"""):
                self.__database.execute( # create table if it doesn't exist
                    """create table tornado_sessions (
                    session_id varchar(64) not null primary key,
                    data longtext,
                    expires integer,
                    ip_address varchar(46),
                    user_agent varchar(255)
                    );""")
                    
        elif url.startswith('postgresql'):
            raise NotImplementedError
        elif url.startswith('sqlite'):
            raise NotImplementedError
        elif url.startswith('memcached'):
            self.__container = session.MemcachedSession
            self.__database = None #TODO - Figure out how to open a memcached session
        elif url.startswith('mongodb'):
            self.__container = session.MongoDBSession
            self.__database = None #TODO - Figure out how to open a mongodb session
        elif url.startswith('redis'):
            self.__container = session.RedisSession
            self.__database = None #TODO - Figure out how to open a redis session
        elif url.startswith('dir'):
            self.__container = session.DirSession
            self.__database = container_url[6:]
        elif url.startswith('file'):
            self.__container = session.FileSession
            self.__database = container_url[7:]
        else:
            return None
            
    def create_session(self, tornado_web):
        """Creates a session handler connection to the persistent storage container
        Current support for: MySQL, Memcached, MongoDB, Redis, Directory, and File sessions"""
        #settings = self.application.settings # just a shortcut
        
        new_session = None
        old_session = None
        
        session_id = tornado_web.get_secure_cookie(self.__kw['cookie_name'])
        ip_address = tornado_web.request.remote_ip
        user_agent = tornado_web.request.headers.get('User-Agent')
        
        kw = {'security_model': self.__kw['security_model'],
              'duration': self.__kw['duration'],
              'ip_address': ip_address,
              'user_agent': user_agent,
              'tornado_web': tornado_web,
              'regeneration_interval': self.__kw['regeneration_interval'],
              'catalog': self.__kw['catalog'],
              'cookie_name': self.__kw['cookie_name']
              }

        old_session = self.__container.load(session_id, self.__database, **kw)

        if old_session is None or old_session._is_expired(): # create a new session
            new_session = self.__container(self.__database, **kw)

        if old_session is not None:
            if old_session._should_regenerate():
                old_session.refresh(new_session_id=True)
            return old_session

        return new_session