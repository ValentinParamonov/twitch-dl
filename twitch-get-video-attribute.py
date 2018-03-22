#!/usr/bin/env python3
import os
from argparse import ArgumentParser
from sys import stdin, stderr, stdout

from twitch.constants import Twitch
from util.contents import Contents


def main():
    try:
        args = parse_args()
        user_id = cmdline_or_stdin(args.user_id)
        video_name = cmdline_or_stdin(args.video_name)
        videos = matching_videos_of(user_id, video_name)
        if args.list_attributes:
            list_attributes_of(videos[0])
        else:
            print_attribute(videos, args.name)
    except ValueError as error:
        stderr.write(str(error) + os.linesep)
        exit(1)


def cmdline_or_stdin(arg):
    return arg if arg else stdin.readline().strip()


def parse_args():
    parser = ArgumentParser()
    parser.add_argument('user_id', nargs='?')
    parser.add_argument('video_name', nargs='?')
    parser.add_argument(
        '-n',
        '--name',
        metavar='NAME',
        help='print video attribute by NAME (defaults to "id")',
        default='id'
    )
    parser.add_argument(
        '-l',
        '--list-attributes',
        help='show the list of attribute names',
        action='store_true',
        default=False
    )
    return parser.parse_args()


def matching_videos_of(user_id, video_name):
    videos = videos_of(user_id)
    matched_videos = list(filter(
        lambda video: video['title'].strip().lower() == video_name.strip().lower(),
        videos
    ))
    if len(matched_videos) == 0:
        raise ValueError('No matching videos found!')
    return matched_videos


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


def list_attributes_of(video):
    for attribute in sorted(video.keys()):
        stdout.write(attribute + os.linesep)


def print_attribute(videos, attribute_name):
    for video in videos:
        if attribute_name not in video:
            raise ValueError('Video has no attribute "{}"'.format(attribute_name))
        video_attribute = video[attribute_name]
        stdout.write(video_attribute + os.linesep)


if __name__ == '__main__':
    main()
