import m3u8
import requests


class Playlist:
    __client_id = {'Client-ID': 'jzkbprff40iqj646a697cyrvl0zt2m6'}

    @classmethod
    def fetch_for(cls, channel):
        token = cls.__fetch_token(channel)
        if token is None:
            return None
        playlist = cls.__fetch_playlist(cls.__playlist_link_for(channel), token)
        if playlist is None:
            return None
        return cls.__best_quality_playlist(playlist.playlists)

    @classmethod
    def __best_quality_playlist(cls, playlists):
        playlists.sort(key=cls.__by_resolution_and_bandwidth)
        best_playlist_uri = playlists[-1].uri
        playlist = cls.__fetch_playlist(best_playlist_uri)
        playlist.base_path = best_playlist_uri.rsplit('/', 1)[0]
        return playlist

    @staticmethod
    def __by_resolution_and_bandwidth(playlist):
        stream_info = playlist.stream_info
        return stream_info.resolution, stream_info.bandwidth

    @classmethod
    def __fetch_token(cls, channel):
        response = requests.get(
            'https://api.twitch.tv/api/channels/{}/access_token'.format(channel),
            headers=cls.__client_id
        )
        if response.status_code != 200:
            return None
        return response.json()

    @staticmethod
    def __playlist_link_for(channel):
        return 'https://usher.ttvnw.net/api/channel/hls/{}.m3u8'.format(channel)

    @staticmethod
    def __fetch_playlist(link, token=None):
        response = requests.get(
            link,
            params={'token': token['token'], 'sig': token['sig']} if token else {}
        )
        if response.status_code != 200:
            return None
        return m3u8.loads(response.content.decode('utf8'))
