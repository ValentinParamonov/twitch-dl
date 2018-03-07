#!/usr/bin/env python3
import os
import sys
from argparse import ArgumentParser

from twitch.constants import Twitch
from twitch.playlist import Playlist
from util.contents import Contents


def main():
    (channel_name, video_name) = parse_args()
    try:
        user_id = user_id_of(channel_name)
        video_id = video_id_of(user_id, video_name)
        playlist = playlist_for(video_id)
        exit(0) if is_muted(playlist) else exit(1)
    except ValueError as error:
        sys.stderr.write(str(error) + os.linesep)
        exit(2)


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        '-c',
        '--channel',
        dest='channel_name',
        metavar='CHANNEL_NAME',
        required=True
    )
    parser.add_argument(
        '-v',
        '--video',
        dest='video_name',
        metavar='VIDEO_NAME',
        required=True
    )
    args = parser.parse_args()
    return args.channel_name, args.video_name


def user_id_of(channel_name):
    data = user_data_for(channel_name)['data']
    if len(data) == 0:
        raise ValueError('User could not be found!')
    return data[0]['id']


def user_data_for(channel_name):
    return Contents.json(
        'https://api.twitch.tv/helix/users',
        params={'login': channel_name},
        headers=Twitch.client_id_header,
        onerror=lambda _: raise_error('Failed to get the users list!')
    )


def raise_error(message):
    raise ValueError(message)


def video_id_of(user_id, video_name):
    videos = videos_of(user_id)
    video = next(
        (
            video for video in videos
            if video['title'].strip().lower() == video_name.strip().lower()
        ),
        None
    )
    if not video:
        raise ValueError('Video could not be found!')
    return video['id']


def videos_of(user_id):
    def fetch_videos(cursor):
        params = {'user_id': user_id, 'first': 100}
        if cursor:
            params['after'] = cursor
        response = Contents.json(
            'https://api.twitch.tv/helix/videos',
            params=params,
            headers=Twitch.client_id_header,
            onerror=lambda _: raise_error('Failed to get the videos list!')
        )
        return response['data'], response['pagination']['cursor']

    videos, next_page = fetch_videos(None)
    while len(videos) > 0:
        for video in videos:
            yield video
        videos, next_page = fetch_videos(next_page)


def playlist_for(video_id):
    return Playlist().fetch_for_vod(video_id)


def is_muted(playlist):
    return any(map(lambda segment: segment.uri.endswith('muted.ts'), playlist.segments))


if __name__ == '__main__':
    main()
