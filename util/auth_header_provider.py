import os

from twitch.constants import Twitch
from util.contents import Contents
from util.log import Log


# Expecting the credentials file to be a text file with
# client_id on the first line and client_secret on the second
class AuthHeaderProvider:
    @classmethod
    def authenticate(cls):
        credentials_file = cls.build_credentials_file_path()
        client_id, client_secret = cls.read_credentials(credentials_file)
        token = Contents.post(
            Twitch.auth_token_url.format(
                client_id=client_id,
                client_secret=client_secret
            )
        ).json()['access_token']
        return {'Client-ID': client_id, 'Authorization': 'Bearer ' + token}

    @staticmethod
    def build_credentials_file_path():
        config_dir = os.environ.get('XDG_CONFIG_HOME') \
                     or os.path.expanduser('~/.config')
        return '{}/tw-dl/credentials'.format(config_dir)

    @staticmethod
    def read_credentials(credentials_file):
        try:
            with open(credentials_file, 'rt') as credentials:
                client_id = credentials.readline().strip()
                client_secret = credentials.readline().strip()
                if not client_id or not client_secret:
                    raise ValueError('empty credentials')
                return client_id, client_secret
        except FileNotFoundError as e:
            Log.fatal(str(e))
