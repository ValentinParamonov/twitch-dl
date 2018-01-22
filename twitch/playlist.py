import m3u8
from m3u8 import M3U8

from twitch.constants import Twitch
from twitch.token import Token
from util.contents import Contents


class Playlist:
    def __init__(self):
        self.__token = Token()
        self.__best_quality_link = None

    def fetch_for_channel(self, channel_name):
        if self.__best_quality_link:
            return self.fetch_playlist(self.__best_quality_link)
        return self.__fetch_new(channel_name)

    def __fetch_new(self, channel_name):
        token = self.__token.fetch_for_channel(channel_name)
        playlist_link = Twitch.channel_playlist_link.format(channel_name)
        return self.__fetch_playlist(playlist_link, token)

    def __fetch_playlist(self, playlist_link, token):
        playlist_container = self.fetch_playlist(playlist_link, token)
        if len(playlist_container.playlists) == 0:
            return playlist_container
        self.__best_quality_link = playlist_container.playlists[0].uri
        return self.fetch_playlist(self.__best_quality_link)

    @staticmethod
    def fetch_playlist(link, token=None):
        params = {'allow_source': 'true'} if token else {}
        params.update(
            {'token': token['token'], 'sig': token['sig']} if token else {}
        )
        raw_playlist = Contents.utf8(link, params=params, onerror=lambda _: None)
        if raw_playlist is None:
            return M3U8(None)
        return m3u8.loads(raw_playlist)

    def fetch_for_vod(self, vod_id):
        token = Token.fetch_for_vod(vod_id)
        playlist_link = Twitch.vod_playlist_link.format(vod_id)
        playlist = self.__fetch_playlist(playlist_link, token)
        playlist.base_path = self.__best_quality_link.rsplit('/', 1)[0]
        return playlist
