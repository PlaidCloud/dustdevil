#!/usr/bin/env python

"""
Sessions module for the Tornado framework.

This module implements sessions for Tornado. It can store
session data in files or MySQL databse, Memcached, Redis
and MongoDB.

USAGE:
======

Every session object can be handled as a dictionary:
    self.session[key] = value
    var = self.session[key]

The session data is saved automatically for you when the request
handler finishes. 

Two utility functions, invalidate() and refresh() are available to
every session object. Read their documentation to learn more.

The application provider is responsible for removing stale, expired
sessions from the storage. However, he can use the delete_expired()
function provided with every storage class except Memcached, which
knows when a session expired and removes it automatically.


SETTINGS:
=========

The session module introduces new settings available to the
application:

session_age: how long should the session be valid (applies also to cookies);
             the value can be anything an integer, string or datetime.timedelta;
             default is 15 mins
             check out _expires_at for additional info

session_regeneration_interval: period, after which the session_id should be
                               regenerated; when the session creation time + period
                               exceed current time, a new session is stored
                               server-side (the sesion data remain unchanged) and
                               the client cookie is refreshed; the old session
                               is no longer valid
                               session regeneration is used to strenghten security
                               and prevent session hijacking; default interval
                               is 4 minutes
                               the setting accepts integer, string or timedelta values,
                               read _next_regeneration_at() documentation for more info

session_cookie_name: the name of the cookie, which stores the session_id;
                     default is 'session_id'

session_cookie_path: path attribute for the session cookie;
                     default is '/'

session_cookie_domain: domain attribute for the session cookie;
                       default is None

session_storage: a string specifying the session storage;
                 available storage engines are: file-based sessions (all sessions
                 are stored in a single file), directory-based sessions (every
                 session is stored in a single file, all in one directory),
                 MySQL-based sessions (sessions are stored in a MySQL database),
                 Redis-based sessions (using Redis to store them, obviously),
                 MongoDB-based sessions (each session stored as a document
                 in MongoDB)

                 if you want to store session data in a single file, set
                 this to a url of the following format:
                 'file:///path/to/session_storage_file'

                 another choice is to store session in a directory, where
                 each session is stored in a separate, single file; to
                 enable this behaviour, set this setting to:
                 dir://[/path/to/session/storage/directory]
                 if you omit the directory path, Tornado will create
                 a temporary directory for you
                 each session will be mapped to a file following the
                 <session_id>.session format, saved in this directory

                 be sure the Tornado process has read & write access to
                 this path, whether it's a file or a directory

                 if you want to use MySQL, set it in this format:
                 'mysql://username:password[@hostname[:port]]/database'

                 to enable Redis as a storage engine, set this setting
                 to 'redis://' with optional password, host, port and database
                 elements (e.g. 'redis://secret@127.0.0.1:8888/1'; if using
                 password with default host, you have to append an @-sign:
                 'redis://secret@/2'); if not complete, defaults are used (
                 localhost:6379, no auth, db 1)
                 remember that you have to have the redis python library
                 available on your system to enable Redis-based sessions

                 to use MongoDB as session storage, set this to a string
                 following the format:
                 'mongodb://[host[:port]]/db
                 If no host or port is specified, defaults are used (localhost,
                 27017)

                 if you don't specify any storage, the default behaviour is
                 to create a new temporary file according to yours OS'
                 conventions (on Unix-like systems in the /tmp directory);
                 the file will have 'tornado_sessions_' as name prefix

session_security_model: not implemented yet;
                        the plan to future versions is to provide some basic
                        mechanisms to prevent session hijacking, based on
                        users IP address, User-Agent, GeoIP or whatever
                        other data; suggestions welcomed
"""

import base64
import csv
import collections
import datetime
import os
import cPickle as pickle
import re
import tempfile
import time
import types

__author__ = "Milan Cermak"
__copyright__ = "Copyright 2009 Milan Cermak"
__credits__ = ["Milan Cermak", "Paul Morel"]
__license__ = "Apache 2.0"
__version__ = "1.0"
__maintainer__ = "Paul Morel"
__email__ = "paul.morel@tartansolutions.com"
__status__ = "Stable"

class BaseSession(collections.MutableMapping):
    """The base class for the session object. Work with the session object
    is really simple, just treat is as any other dictionary:

    class Handler(tornado.web.RequestHandler):
        def get(self):
            var = self.session['key']
            self.session['another_key'] = 'value'

    Session is automatically saved on handler finish. Session expiration
    is updated with every request. If configured, session ID is
    regenerated periodically.

    The session_id attribute stores a unique, random, 64 characters long
    string serving as an indentifier.

    To create a new storage system for the sessions, subclass BaseSession
    and define save(), load() and delete(). For inspiration, check out any
    of the already available classes and documentation to aformentioned functions."""
    def __init__(self, session_id=None, data=None, security_model=[], expires=None,
                 duration=None, ip_address=None, user_agent=None, catalog=None,
                 regeneration_interval=None, next_regeneration=None, tornado_web=None, 
                 cookie_name=None, **kwargs):
        # if session_id is True, we're loading a previously initialized session
        if session_id:
            self.session_id = session_id
            self.data = data
            self.duration = duration
            self.expires = expires
            self.dirty = False
        else:
            self.session_id = self._generate_session_id()
            self.data = {}
            self.duration = duration
            self.expires = self._expires_at()
            self.dirty = True

        self.ip_address = ip_address
        self.user_agent = user_agent
        self.security_model = security_model
        self.regeneration_interval = regeneration_interval
        self.next_regeneration = next_regeneration or self._next_regeneration_at()
        self._delete_cookie = False
        self._catalog = catalog
        self._tornado_web = tornado_web
        self._cookie_name = cookie_name

    def __repr__(self):
        return '<session id: %s data: %s>' % (self.session_id, self.data)

    def __str__(self):
        return self.session_id

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value
        self.dirty = True

    def __delitem__(self, key):
        del self.data[key]
        self.dirty = True

    def keys(self):
        return self.data.keys()

    def __iter__(self):
        return self.data.__iter__()

    def __len__(self):
        return len(self.data.keys())

    def _generate_session_id(cls):
        return os.urandom(32).encode('hex') # 256 bits of entropy

    def _is_expired(self):
        """Check if the session has expired."""
        return datetime.datetime.now() > self.expires

    def _expires_at(self):
        """Find out the expiration time. Returns datetime.datetime."""
        v = self.duration
        if isinstance(v, datetime.timedelta):
            pass
        elif isinstance(v, (int, long)):
            self.duration =  datetime.timedelta(seconds=v)
        elif isinstance(v, basestring):
            self.duration = datetime.timedelta(seconds=int(v))
        else:
            self.duration = datetime.timedelta(seconds=900) # 15 mins

        return datetime.datetime.now() + self.duration

    def _should_regenerate(self):
        """Determine if the session_id should be regenerated."""
        return datetime.datetime.now() > self.next_regeneration

    def _next_regeneration_at(self):
        """Return a datetime object when the next session id regeneration
        should occur."""
        # convert whatever value to an timedelta (period in seconds)
        # store it in self.regeneration_interval to prevent
        # converting in later calls and return the datetime
        # of next planned regeneration
        v = self.regeneration_interval
        if isinstance(v, datetime.timedelta):
            pass
        elif isinstance(v, (int, long)):
            self.regeneration_interval = datetime.timedelta(seconds=v)
        elif isinstance(v, basestring):
            self.regeneration_interval = datetime.timedelta(seconds=int(v))
        else:
            self.regeneration_interval = datetime.timedelta(seconds=240) # 4 mins

        return datetime.datetime.now() + self.regeneration_interval

    def invalidate(self): 
        """Destorys the session, both server-side and client-side.
        As a best practice, it should be used when the user logs out of
        the application."""
        self.delete() # remove server-side
        self._delete_cookie = True # remove client-side
    
    def refresh(self, duration=None, new_session_id=False): # the opposite of invalidate
        """Prolongs the session validity. You can specify for how long passing a
        value in the duration argument (the same rules as for session_age apply).
        Be aware that henceforward this particular session may have different
        expiry date, not respecting the global setting. 
        
        If new_session_id is True, a new session identifier will be generated.
        This should be used e.g. on user authentication for security reasons."""
        if duration:
            self.duration = duration
            self.expires = self._expires_at()
        else:
            self.expires = self._expires_at()
        if new_session_id:
            self.delete()
            self.session_id = self._generate_session_id()
            self.next_regeneration = self._next_regeneration_at()
        self.dirty = True # force save
        self.save()

    def save(self):
        """Save the session data and metadata to the backend storage
        if necessary (self.dirty == True). On successful save set
        dirty to False."""
        pass
        
    def finish(self):
        if self._delete_cookie:
            self._tornado_web.clear_cookie(self._cookie_name)
        else:
            self.refresh() # advance expiry time and save session
            self._tornado_web.set_secure_cookie(self._cookie_name,
                                   self.session_id,
                                   #expires_days=None,
                                   #expires=my_container.session.expires,
                                   path='/')
        
    @staticmethod
    def load(session_id, location):
        """Load the stored session from storage backend or return
        None if the session was not found, in case of stale cookie."""
        pass

    def delete(self):
        """Remove all data representing the session from backend storage."""
        pass

    @staticmethod
    def delete_expired(file_path):
        """Deletes sessions with timestamps in the past form storage."""
        pass

    def serialize(self):
        dump = {'session_id': self.session_id,
                'data': self.data,
                'duration': self.duration,
                'expires': self.expires,
                'ip_address': self.ip_address,
                'user_agent': self.user_agent,
                'security_model': self.security_model,
                'regeneration_interval': self.regeneration_interval,
                'next_regeneration': self.next_regeneration}
        return base64.encodestring(pickle.dumps(dump))

    @staticmethod
    def deserialize(datastring):
        return pickle.loads(base64.decodestring(datastring))


class FileSession(BaseSession):
    """File based session storage. Sessions are stored in CSV format. The file
    is either specified in the session_storage setting (be sure it is writable
    to the Tornado process) or a new tempfile with 'tornado_sessions_' prefix
    is created in the OS' standard location.
    
    Be aware that file-based sessions can get really slow with many stored
    session as any action (save, load, delete) has to cycle through the whole
    file. """
    def __init__(self, file_path, **kwargs):
        super(FileSession, self).__init__(**kwargs)
        self.file_path = file_path
        if not kwargs.has_key('session_id'):
            self.save() # save only if it is a newly created session, not if loaded from storage

    def save(self):
        """Save the session. To prevent data loss, we read from the original
        file and write the updated data to a temporary file. When all data is
        written, we rename the temporary file to the original. """
        if not self.dirty:
            return
        found = False
        reader_file = open(self.file_path, 'rb')
        reader = csv.DictReader(reader_file,
                                fieldnames=['session_id', 'data', 'expires', 'ip_address', 'user-agent'])
        writer_temp = tempfile.mkstemp()[1]
        writer_temp_file = open(writer_temp, 'w+b')
        writer = csv.DictWriter(writer_temp_file,
                                ['session_id', 'data', 'expires', 'ip_address', 'user-agent'])
        for line in reader:
            if line['session_id'] == self.session_id:
                writer.writerow({'session_id': self.session_id,
                                 'data': self.serialize(),
                                 'expires': int(time.mktime(self.expires.timetuple())),
                                 'ip_address': self.ip_address,
                                 'user-agent': self.user_agent})
                found = True
            else:
                writer.writerow(line)

        if not found: # not previously stored session
            # column data will contain the whole object, not just the
            # data attribute
            writer.writerow({'session_id': self.session_id,
                             'data': self.serialize(),
                             'expires': int(time.mktime(self.expires.timetuple())),
                             'ip_address': self.ip_address,
                             'user-agent': self.user_agent})
        reader_file.close()
        writer_temp_file.close()
        os.rename(writer_temp, self.file_path)
        self.dirty = False

    @staticmethod
    def load(session_id, path):
        """Loads a session from the specified file."""
        try:
            reader_file = open(path, 'rb')
            reader = csv.DictReader(reader_file,
                                    fieldnames=['session_id', 'data', 'expires', 'ip_address', 'user-agent'])
            for line in reader:
                if line['session_id'] == session_id:
                    reader_file.close()
                    kwargs = FileSession.deserialize(line['data'])
                    return FileSession(path, **kwargs)
            reader_file.close()
            return None
        except:
            return None

    def delete(self):
        """Remove the session from the storage file. File manipulation is
        done the same way as in save()."""
        reader_file = open(self.file_path, 'rb')
        reader = csv.DictReader(reader_file,
                                fieldnames=['session_id', 'data', 'expires', 'ip_address', 'user-agent'])
        writer_temp = tempfile.mkstemp()[1]
        writer_temp_file = open(writer_temp, 'w+b')
        writer = csv.DictWriter(writer_temp_file,
                                ['session_id', 'data', 'expires', 'ip_address', 'user-agent'])
        for line in reader:
            if line['session_id'] != self.session_id:
                writer.writerow(line)

        reader_file.close()
        writer_temp_file.close()
        os.rename(writer_temp, self.file_path) # rename the temporary holder to the session file

    @staticmethod
    def delete_expired(file_path):
        reader_file = open(file_path, 'rb')
        reader = csv.DictReader(reader_file,
                                fieldnames=['session_id', 'data', 'expires', 'ip_address', 'user-agent'])
        writer_temp = tempfile.mkstemp()[1]
        writer_temp_file = open(writer_temp, 'w+b')
        writer = csv.DictWriter(writer_temp_file,
                                ['session_id', 'data', 'expires', 'ip_address', 'user-agent'])
        for line in reader:
            if int(line['expires']) > int(time.time()):
                writer.writerow(line)

        reader_file.close()
        writer_temp_file.close()
        os.rename(writer_temp, file_path)

class DirSession(BaseSession):
    """A "directory" based session storage. Every session is stored in a
    separate file, so one file represents one session. The files are
    named as the session_id plus '.session' suffix. Data is stored in
    CSV format. Make sure the directory where the files are stored is
    readable and writtable to the Tornado process."""
    def __init__(self, dir_path, **kwargs):
        super(DirSession, self).__init__(**kwargs)
        self.dir_path = dir_path
        if not kwargs.has_key('session_id'):
            self.save()

    def save(self):
        """Save the session to a file. The algorithm first writes to a temp
        file created in the sessions directory. When all data is written,
        it renames it to the correct name (<session_id>.session)."""
        if not self.dirty:
            return
        session_file = os.path.join(self.dir_path, self.session_id+'.session')
        # write to temp file and then rename
        temp_fd, temp_name = tempfile.mkstemp(dir=self.dir_path)
        temp_file = os.fdopen(temp_fd, 'w+b')
        writer = csv.writer(temp_file)
        writer.writerow([self.session_id,
                         self.serialize(),
                         int(time.mktime(self.expires.timetuple())),
                         self.ip_address,
                         self.user_agent])
        temp_file.close()
        os.rename(temp_name, session_file)
        self.dirty = False

    @staticmethod
    def load(session_id, directory):
        """Load session from file storage."""
        try:
            session_file_name = os.path.join(directory, session_id+'.session')
            if os.path.isfile(session_file_name):
                session_file = open(session_file_name, 'rb')
                reader = csv.reader(session_file)
                l = reader.next()
                kwargs = DirSession.deserialize(l[1])
                return DirSession(directory, **kwargs)
            return None
        except:
            return None

    def delete(self):
        """Deletes the session file."""
        session_file = os.path.join(self.dir_path, self.session_id+'.session')
        if os.path.isfile(session_file):
            os.remove(session_file)

    @staticmethod
    def delete_expired(dir_path):
        assert os.path.isdir(dir_path)
        all_files = os.listdir(dir_path)
        session_files = filter(lambda x: x.endswith('.session'), all_files)
        for s in session_files:
            name = os.path.join(dir_path, s)
            session_file = open(name, 'rb')
            reader = csv.reader(session_file)
            data = reader.next()
            session_file.close()
            if int(data[2]) < int(time.time()):
                os.remove(name)


class MySQLSession(BaseSession):
    """Enables MySQL to act as a session storage engine. It uses Tornado's
    MySQL wrapper from database.py.

    The connection details are specified in the session_storage settings
    as string mysql://username:password[@hostname[:port]]/database. It
    stores session data in the table tornado_sessions. If hostname or
    port aren't specified, localhost:3306 are used as defaults. """

    def __init__(self, connection, **kwargs):
        super(MySQLSession, self).__init__(**kwargs)
        self.connection = connection
        if not kwargs.has_key('session_id'):
            self.save()

    @staticmethod
    def _parse_connection_details(details):
        # mysql://username:password[@hostname[:port]]/db

        if details.find('@') != -1:
            match = re.match('mysql://(\w+):(.*?)@([\w|\.]+)(?::(\d+))?/(\S+)', details)
            username = match.group(1)
            password = match.group(2)
            hostname = match.group(3)
            port = match.group(4) or '3306'
            database = match.group(5)
            host_port = hostname + ':' + port
        else: # hostname and port not specified
            host_port = 'localhost:3306'
            match = re.match('mysql://(\w+):(.*?)/(\S+)', details)
            username = match.group(1)
            password = match.group(2)
            database = match.group(3)        

        return username, password, host_port, database

    def save(self):
        """Store the session data to database. Session is saved only if it
        is necessary. If the table 'tornado_sessions' does not exist yet,
        create it. It uses MySQL's "non-standard insert ... on duplicate key
        "update query."""
        if not self.dirty:
            return

        self.connection.execute( # MySQL's upsert
            """insert into tornado_sessions
            (session_id, data, expires, ip_address, user_agent) values
            (%s, %s, %s, %s, %s)
            on duplicate key update
            session_id=values(session_id), data=values(data), expires=values(expires),
            ip_address=values(ip_address), user_agent=values(user_agent);""",
            self.session_id, self.serialize(), int(time.mktime(self.expires.timetuple())),
            self.ip_address, self.user_agent)
            
        print "Session ID sent in the SAVE QUERY = ", self.session_id
        self.dirty = False

    @staticmethod
    def load(session_id, connection, **kwargs):
        """Load the stored session."""
        try:
            data = connection.get("""
            select session_id, data, expires, ip_address, user_agent
            from tornado_sessions where session_id = %s;""",  session_id)
            if data:
                stored_kwargs = MySQLSession.deserialize(data['data'])
                kwargs.update(stored_kwargs)
                session_object = MySQLSession(connection, **kwargs)
                #session_object._tornado_web = tornado_web
            #print "Data from query", data
            return session_object
        except:
            return None

    def delete(self):
        """Remove session data from the database."""
        self.connection.execute("""
        delete from tornado_sessions where session_id = %s;""", self.session_id)

    @staticmethod
    def delete_expired(connection):
        connection.execute("""
        delete from tornado_sessions where expires < %s;""", int(time.time()))


try:
    import redis

    class RedisSession(BaseSession):
        """Class handling session storing in Redis.

        It uses default Redis settings for host and port, without
        authentication. The session_id is used as a key to a string
        value holding the session details. The value has a format of
        serialized_session_object_data:expires:ip_address:user_agent.

        The save() and delete() methods both trigger BGSAVE. Be sure
        you're aware of possible limitations (saving is not guaranteed
        in the unfortunate case of a failure between the call to BGSAVE
        and actual writing data to HDD by Redis)."""

        def __init__(self, connection, **kwargs):
            super(RedisSession, self).__init__(**kwargs)
            self.connection = connection
            if not kwargs.has_key('session_id'):
                self.save()

        @staticmethod
        def _parse_connection_details(details):
            # redis://[auth@][host[:port]][/db]
            match = re.match('redis://(?:(\S+)@)?([^\s:/]+)?(?::(\d+))?(?:/(\d+))?$', details)
            password, host, port, db = match.groups()
            return password, host, port, db

        def save(self):
            """Save the current sesssion to Redis. The session_id
            acts as a key. The value is constructed of colon separated values
            serialized_data, expires, ip_address and user_agent. This
            function calls BGSAVE on Redis, so it may terminate before
            the data is actually updated on the HDD."""
            if not self.dirty:
                return
            value = ':'.join((self.serialize(),
                             str(int(time.mktime(self.expires.timetuple()))),
                             self.ip_address,
                             self.user_agent))
            self.connection.set(self.session_id, value)
            try:
                self.connection.save(background=True)
            except redis.ResponseError:
                pass
            self.dirty = False

        @staticmethod
        def load(session_id, connection):
            """Load the stored session."""
            if connection.exists(session_id) == 1:
                try:
                    data = connection.get(session_id)
                    kwargs = RedisSession.deserialize(data.split(':', 1)[0])
                    return RedisSession(connection, **kwargs)
                except:
                    return None
            return None

        def delete(self):
            """Delete the session key-value from Redis. As save(),
            delete() too calls BGSAVE."""
            self.connection.delete(self.session_id)
            try:
                self.connection.save(background=True)
            except redis.ResponseError:
                pass

        @staticmethod
        def delete_expired(connection):
            for key in connection.keys('*'):
                value = connection.get(key)
                expires = value.split(':', 2)[1]
                if int(expires) < int(time.time()):
                    connection.delete(key)

except ImportError:
    pass


try:
    import pymongo

    class MongoDBSession(BaseSession):
        """Class implementing the MongoDB based session storage.
        All sessions are stored in a collection "tornado_sessions" in the db
        you specify in the session_storage setting.

        The session document structure is following:
        'session_id': session ID
        'data': serialized session object
        'expires': a timestamp of when the session expires, in sec since epoch
        'user_agent': self-explanatory
        An index on session_id is created automatically, on application's init.

        The end_request() is called after every operation (save, load, delete),
        to return the connection back to the pool.
        """

        def __init__(self, db, **kwargs):
            super(MongoDBSession, self).__init__(**kwargs)
            self.db = db # an instance of pymongo.collection.Collection
            if not kwargs.has_key('session_id'):
                self.save()

        @staticmethod
        def _parse_connection_details(details):
            # mongodb://[host[:port]]/db
            match = re.match('mongodb://([\S|\.]+?)?(?::(\d+))?/(\S+)', details)
            return match.group(1), match.group(2), match.group(3) # host, port, database

        def save(self):
            """Upsert a document to the tornado_sessions collection.
            The document's structure is like so:
            {'session_id': self.session_id,
             'data': self.serialize(),
             'expires': int(time.mktime(self.expires.timetuple())),
             'user_agent': self.user_agent}
            """
            # upsert
            self.db.update(
                {'session_id': self.session_id}, # equality criteria
                {'session_id': self.session_id,
                 'data': self.serialize(),
                 'expires': int(time.mktime(self.expires.timetuple())),
                 'user_agent': self.user_agent}, # new document
                upsert=True)
            self.db.database.connection.end_request()

        @staticmethod
        def load(session_id, db):
            """Load session from the storage."""
            try:
                data = db.find_one({'session_id': session_id})
                if data:
                    kwargs = MongoDBSession.deserialize(data['data'])
                    db.database.connection.end_request()
                    return MongoDBSession(db, **kwargs)
                db.database.connection.end_request()
                return None
            except:
                db.database.connection.end_request()
                return None

        def delete(self):
            """Remove session from the storage."""
            self.db.remove({'session_id': self.session_id})
            self.db.database.connection.end_request()

        @staticmethod
        def delete_expired(db):
            db.remove({'expires': {'$lte': int(time.time())}})

except ImportError:
    pass



try:
    import pylibmc

    class MemcachedSession(BaseSession):
        """Class responsible for Memcached stored sessions. It uses the
        pylibmc library because it's fast. It communicates with the
        memcached server through the binary protocol and uses async
        I/O (no_block set to 1) to speed things up even more.

        Session ID is used as a key. The value consists of colon
        separated values of serializes session object, expiry timestamp,
        IP address and User-Agent.

        Values are stored with timeout set to the difference between
        saving time and expiry time in seconds. Therefore, no
        old sessions will be held in Memcached memory."""

        def __init__(self, connection, **kwargs):
            super(MemcachedSession, self).__init__(**kwargs)
            self.connection = connection
            if not kwargs.has_key('session_id'):
                self.save()

        @staticmethod
        def _parse_connection_details(details):
            if len(details) > 12:
                return re.sub('\s+', '', details[12:]).split(',')
            else:
                return ['127.0.0.1']

        def save(self):
            """Write the session to Memcached. Session ID is used as
            key, value is constructed as colon separated values of
            serialized session, session expiry timestamp, ip address
            and User-Agent.
            The value is not stored indefinitely. It's expiration time
            in seconds is calculated as the difference between the saving
            time and session expiry."""
            if not self.dirty:
                return
            value = ':'.join((self.serialize(),
                              str(int(time.mktime(self.expires.timetuple()))),
                              self.ip_address,
                              self.user_agent))
            # count how long should it last and then add or rewrite
            live_sec = self.expires - datetime.datetime.now()
            self.connection.set(self.session_id, value, time=live_sec.seconds) 
            self.dirty = False

        @staticmethod
        def load(session_id, connection):
            """Load the session from storage."""
            try:
                value = connection.get(session_id)
                if value:
                    data = value.split(':', 1)[0]
                    kwargs = MemcachedSession.deserialize(data)
                    return MemcachedSession(connection, **kwargs)
            except:
                return None
            return None

        def delete(self):
            """Delete the session from storage."""
            self.connection.delete(self.session_id)

        def delete_expired(connection):
            """With Memcached as session storage, this function does
            not make sense as all keys are saved with expiry time
            exactly the same as the session's. Hence Memcached takse
            care of cleaning out the garbage."""
            raise NotImplementedError

except ImportError:
    pass
