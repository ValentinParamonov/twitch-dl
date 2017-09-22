from util.contents import Contents
from twitch.constants import Twitch


class Token:
    @classmethod
    def fetch_for_channel(cls, channel_name):
        return cls.__fetch(Twitch.channel_token_link.format(channel_name))

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
