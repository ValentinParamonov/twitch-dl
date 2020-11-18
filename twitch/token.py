import json
from time import time

from twitch.constants import Twitch
from util.contents import Contents
from util.persistent_resource import PersistentJsonResource


class Token:
    __expiration_buffer_seconds = 5
    __token_file_name = '~/.cache/twitch-dl/{}.json'

    def __init__(self):
        self.__token_resource = None

    def fetch_for_channel(self, channel_name):
        if not self.__token_resource:
            token_file_name = self.__token_file_name.format(channel_name)
            self.__token_resource = PersistentJsonResource(token_file_name)
        if not self.__token_resource.value() or \
                self.__is_expired(self.__token_resource.value()):
            self.__fetch_and_store_token(channel_name)
        return self.__token_resource.value()

    @staticmethod
    def __is_expired(token):
        token_expiration_ms = json.loads(token['token'])['expires']
        return token_expiration_ms + Token.__expiration_buffer_seconds < time()

    @classmethod
    def __fetch(cls, link):
        return Contents.json(
            link,
            headers=Twitch.client_id_header,
            onerror=lambda _: None
        )

    def __fetch_and_store_token(self, channel_name):
        token = self.__fetch(Twitch.channel_token_link.format(channel_name))
        if token:
            self.__token_resource.store(token)

    @classmethod
    def fetch_for_vod(cls, vod_id):
        return cls.__fetch(Twitch.vod_token_link.format(vod_id))
