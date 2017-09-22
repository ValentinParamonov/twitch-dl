class Twitch:
    channel_playlist_link = 'https://usher.ttvnw.net/api/channel/hls/{}.m3u8'
    vod_playlist_link = 'http://usher.justin.tv/vod/{}'
    channel_token_link = 'https://api.twitch.tv/api/channels/{}/access_token'
    vod_token_link = 'https://api.twitch.tv/api/vods/{}/access_token'
    stream_link = 'https://api.twitch.tv/kraken/streams/{}'
    client_id_header = {'Client-ID': 'jzkbprff40iqj646a697cyrvl0zt2m6'}
