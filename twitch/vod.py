from twitch.constants import Twitch
from util.auth_header_provider import AuthHeaderProvider
from util.contents import Contents


class Vod:
    @staticmethod
    def title(vod_id):
        return Contents.json(
            Twitch.videos_url,
            params={'id': vod_id},
            headers=AuthHeaderProvider.authenticate(),
        )['data'][0]['title']
