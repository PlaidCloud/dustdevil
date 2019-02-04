# pylint: disable=redefined-outer-name
import pytest
from redis.sentinel import Sentinel
from tornado import web
from dustdevil import handler

# @pytest.fixture
# def client():
#     pass

# TODO: This should probably be driven by config.
TEST_SETTINGS = {
    # session_storage is the redis connection string to test.
    'session_storage': 'redis://mymaster@redis-ha/0',
    'security_model': [],
    'duration': int(60 * 60 * 24),  # 24 Hours
    'session_age': int(60 * 60 * 24),  # 24 Hours
    'ip_address': '127.0.0.1',
    'user_agent': 'SuperCoolBrowser/v1',
    'tornado_web': None,
    'regeneration_interval': 60 * 60 * 24 * 365,  # 1 Year,
    'catalog': 'tornado_sessions',
    'cookie_name': 'some_session',
    'field_store': {
        'UserID': 'USER_ID',
        'GroupName': 'GROUP_NAME',
        'UserName': 'USER_NAME',
        'UserFullName': 'NAME'
    },
}

def test_sentinel(capsys):
    session_handler = handler.Handler(TEST_SETTINGS)

    session = session_handler.storage_class.load(
        'something', session_handler.storage_client, **TEST_SETTINGS)

    with capsys.disabled():
        print(session)

    # user_id = self.session.get('USER_ID', 'Unknown')
    # client_ip = self.request.headers.get('X-Real-Ip', 'Unknown')