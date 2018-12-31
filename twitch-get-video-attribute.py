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
            print_attributes(videos, args.name)
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
        help="""
            print video attribute by it\'s NAME. 
            Specify multiple times for a list. (defaults to "id")
            """,
        action='append',
        default=[]
    )
    parser.add_argument(
        '-l',
        '--list-attributes',
        help='show the list of attribute names',
        action='store_true',
        default=False
    )
    args = parser.parse_args()
    args.name = args.name if len(args.name) != 0 else ['id']
    return args


def matching_videos_of(user_id, video_name):
    videos = videos_of(user_id)
    matched_videos = list(filter(
        lambda video: video_name.strip().lower() in video['title'].strip().lower(),
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
        video_entries = response['data']
        pagination = response['pagination']
        cursor = pagination['cursor'] if 'cursor' in pagination else None
        return video_entries, cursor

    videos, next_page = fetch_videos(None)
    while len(videos) > 0:
        for video in videos:
            yield video
        if next_page is not None:
            videos, next_page = fetch_videos(next_page)
        else:
            videos = []


def raise_error(message):
    raise ValueError(message)


def list_attributes_of(video):
    for attribute in sorted(video.keys()):
        stdout.write(attribute + os.linesep)


def print_attributes(videos, attribute_names):
    for video in videos:
        attribute_values = map(lambda a: get_attribute(video, a), attribute_names)
        stdout.write(' '.join(attribute_values) + os.linesep)


def get_attribute(video, attribute_name):
    if attribute_name not in video:
        raise ValueError('Video has no attribute "{}"'.format(attribute_name))
    return video[attribute_name]


if __name__ == '__main__':
    main()
