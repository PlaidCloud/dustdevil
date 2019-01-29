# pylint: disable=redefined-outer-name
import pytest
import redis
from dustdevil import handler

# @pytest.fixture
# def client():
#     pass

def test_sentinel(capsys):
    # Use this to print output stdout *during* tests.
    # with capsys.disabled():
    #     pass

    DUST_DEVIL_SETTINGS = {
        # Because this module is structured different from some other handler
        # modules, we can't get the Plaid config from the Tornado settings right
        # here. We can, however, use cockpit.core.config directly.
        'session_storage': 'redis://plaid@redis-redis-ha/0',
        'session_catalog': 'tornado_sessions',
        'session_cookie_name': 'plaidcloud_session',
        'session_regeneration_interval': 60 * 60 * 24 * 365,  # 1 Year
        'duration': int(60 * 60 * 24),  # 24 hours
        'session_field_store': {
            'UserID': 'USER_ID',
            'PlaidGroup': 'PLAID_GROUP',
            'UserName': 'USER_NAME',
            'UserFullName': 'NAME'
        },
    }

    handle = handler.Handler(DUST_DEVIL_SETTINGS)
    print(handle)
    assert handle
    # sessionx = dust_devil.create_session(self, 'test-session')
    # print(self.sessionx.dump_dict)

    # user_id = self.session.get('USER_ID', 'Unknown')
    # client_ip = self.request.headers.get('X-Real-Ip', 'Unknown')