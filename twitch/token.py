import json
from time import time

from twitch.constants import Twitch
from util.contents import Contents


class Token:
    __expiration_buffer_ms = 5000

    def __init__(self):
        self.__token = None

    def fetch_for_channel(self, channel_name):
        if not self.__token or self.__is_expired(self.__token):
            self.__token = self.__fetch(Twitch.channel_token_link.format(channel_name))
        return self.__token

    @staticmethod
    def __is_expired(token):
        token_expiration_ms = json.loads(token['token'])['expires']
        return token_expiration_ms - Token.__expiration_buffer_ms < time()

    @classmethod
    def __fetch(cls, link):
        return Contents.json(
            link,
            headers=Twitch.client_id_header,
            onerror=lambda _: None
        )

    @classmethod
    def fetch_for_vod(cls, vod_id):
        return cls.__fetch(Twitch.vod_token_link.format(vod_id))
