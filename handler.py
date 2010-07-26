#!/usr/bin/env python

import session

__author__ = "Paul Morel"
__copyright__ = "Copyright 2010 Tartan Solutions, Inc"
__credits__ = ["Paul Morel", "Brian McFadden"]
__license__ = "Apache 2.0"
__version__ = "1.0"
__maintainer__ = "Paul Morel"
__email__ = "paul.morel@tartansolutions.com"
__status__ = "Alpha"

def create_session(session_id, settings, ip_address, user_agent):
    """Creates a session handler connection to the persistent storage container
    Current support for: MySQL, Memcached, MongoDB, Redis, Directory, and File sessions"""
    #settings = self.application.settings # just a shortcut
    
    url = settings.get('session_storage')
    #session_id = self.get_secure_cookie(settings.get('session_cookie_name', 'session_id'))
    kw = {'security_model': settings.get('session_security_model', []),
          'duration': settings.get('session_age', 900),
          'ip_address': ip_address,
          'user_agent': user_agent,
          'regeneration_interval': settings.get('session_regeneration_interval', 240)
          }
    new_session = None
    old_session = None

    if url.startswith('mysql'):
        old_session = session.MySQLSession.load(session_id, settings['_db'])
        if old_session is None or old_session._is_expired(): # create a new session
            new_session = session.MySQLSession(settings['_db'], **kw)
    elif url.startswith('postgresql'):
        raise NotImplementedError
    elif url.startswith('sqlite'):
        raise NotImplementedError
    elif url.startswith('memcached'):
        old_session = session.MemcachedSession.load(session_id, settings['_db'])
        if old_session is None or old_session._is_expired(): # create new session
            new_session = session.MemcachedSession(settings['_db'], **kw)
    elif url.startswith('mongodb'):
        old_session = session.MongoDBSession.load(session_id, settings['_db'])
        if old_session is None or old_session._is_expired(): # create new session
            new_session = session.MongoDBSession(settings['_db'], **kw)
    elif url.startswith('redis'):
        old_session = session.RedisSession.load(session_id, settings['_db'])
        if old_session is None or old_session._is_expired(): # create new session
            new_session = session.RedisSession(settings['_db'], **kw)
    elif url.startswith('dir'):
        dir_path = url[6:]
        old_session = session.DirSession.load(session_id, dir_path)
        if old_session is None or old_session._is_expired(): # create new session
            new_session = session.DirSession(dir_path, **kw)
    elif url.startswith('file'):
        file_path = url[7:]
        old_session = session.FileSession.load(session_id, file_path)
        if old_session is None or old_session._is_expired(): # create new session
            new_session = session.FileSession(file_path, **kw)
    else:
        return None

    if old_session is not None:
        if old_session._should_regenerate():
            old_session.refresh(new_session_id=True)
            # TODO: security checks
        return old_session

    return new_session