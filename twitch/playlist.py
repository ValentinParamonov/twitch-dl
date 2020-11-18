import m3u8
from m3u8 import M3U8

from twitch.constants import Twitch
from twitch.token import Token
from util.contents import Contents
from util.persistent_resource import PersistentJsonResource


class Playlist:
    __playlist_link_file = '~/.cache/twitch-dl/{}-playlist-link.json'

    def __init__(self):
        self.__token = Token()
        self.__best_quality_link_resource = None

    def fetch_for_channel(self, channel_name):
        if not self.__best_quality_link_resource:
            self.__best_quality_link_resource = PersistentJsonResource(
                self.__playlist_link_file.format(channel_name)
            )
            if self.__best_quality_link_resource.value():
                self.__try_playlist_link()
        if not self.__best_quality_link_resource.value():
            return self.__fetch_new(channel_name)
        return self.fetch_playlist(self.__best_quality_link_resource.value())

    def __try_playlist_link(self):
        playlist = self.fetch_playlist(self.__best_quality_link_resource.value())
        if len(playlist.segments) == 0:
            self.__best_quality_link_resource.clear()

    def __fetch_new(self, channel_name):
        token = self.__token.fetch_for_channel(channel_name)
        playlist_link = Twitch.channel_playlist_link.format(channel_name)
        return self.__fetch_playlist(playlist_link, token)

    def __fetch_playlist(self, playlist_link, token):
        playlist_container = self.fetch_playlist(playlist_link, token)
        if len(playlist_container.playlists) == 0:
            return playlist_container
        self.__best_quality_link_resource.store(playlist_container.playlists[0].uri)
        return self.fetch_playlist(self.__best_quality_link_resource.value())

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
        playlist.base_path = self.__best_quality_link_resource.value().rsplit('/', 1)[0]
        return playlist
