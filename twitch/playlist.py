import m3u8
from twitch.token import Token
from util.contents import Contents
from twitch.constants import Twitch


class Playlist:
    @classmethod
    def fetch_for_channel(cls, channel_name):
        token = Token.fetch_for_channel(channel_name)
        playlist_link = Twitch.channel_playlist_link.format(channel_name)
        return cls.__fetch_playlist(playlist_link, token)

    @classmethod
    def __fetch_playlist(cls, playlist_link, token):
        playlist = cls.fetch_playlist(playlist_link, token)
        if playlist is None:
            return None
        return cls.__best_quality_playlist(playlist.playlists)

    @classmethod
    def __best_quality_playlist(cls, playlists):
        playlists.sort(key=cls.__by_resolution_and_bandwidth)
        best_playlist_uri = playlists[-1].uri
        playlist = cls.fetch_playlist(best_playlist_uri)
        playlist.base_path = best_playlist_uri.rsplit('/', 1)[0]
        return playlist

    @staticmethod
    def __by_resolution_and_bandwidth(playlist):
        stream_info = playlist.stream_info
        return stream_info.resolution, stream_info.bandwidth

    @staticmethod
    def fetch_playlist(link, token=None):
        params = {'allow_source': 'true'}
        params.update(
            {'token': token['token'], 'sig': token['sig']} if token else {}
        )
        raw_playlist = Contents.utf8(link, params=params, onerror=lambda _: None)
        if raw_playlist is None:
            return None
        return m3u8.loads(raw_playlist)

    @classmethod
    def fetch_for_vod(cls, vod_id):
        token = Token.fetch_for_vod(vod_id)
        playlist_link = Twitch.vod_playlist_link.format(vod_id)
        playlist = cls.__fetch_playlist(playlist_link, token)
        return playlist
