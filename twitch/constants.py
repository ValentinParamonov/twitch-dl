class Twitch:
    channel_playlist_link = 'https://usher.ttvnw.net/api/channel/hls/{}.m3u8?player_backend=mediaplayer'
    vod_playlist_link = 'http://usher.justin.tv/vod/{}'
    channel_token_link = 'https://api.twitch.tv/api/channels/{}/access_token?oauth_token=undefined&need_https=true&platform=web&player_type=site&player_backend=mediaplayer'
    vod_token_link = 'https://api.twitch.tv/api/vods/{}/access_token'
    stream_link = 'https://api.twitch.tv/helix/streams'
    client_id_header = {'Client-ID': 'jzkbprff40iqj646a697cyrvl0zt2m6'}
    auth_token_url = 'https://id.twitch.tv/oauth2/token?grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}'
    users_url = 'https://api.twitch.tv/helix/users'
    videos_url = 'https://api.twitch.tv/helix/videos'
