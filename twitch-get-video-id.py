#!/usr/bin/env python3
import os
import sys

from twitch.constants import Twitch
from util.contents import Contents


def main():
    try:
        user_id = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.readline().strip()
        video_name = sys.stdin.readline().strip()
        video_id = video_id_of(user_id, video_name)
        sys.stdout.write(video_id + os.linesep)
    except ValueError as error:
        sys.stderr.write(str(error) + os.linesep)
        exit(1)


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


def raise_error(message):
    raise ValueError(message)


if __name__ == '__main__':
    main()
