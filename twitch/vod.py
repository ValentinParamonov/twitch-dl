from util.contents import Contents
from twitch.constants import Twitch


class Vod:
    @staticmethod
    def title(vod_id):
        return Contents.json(
            'https://api.twitch.tv/kraken/videos/v{}'.format(vod_id),
            headers=Twitch.client_id_header
        )['title']
