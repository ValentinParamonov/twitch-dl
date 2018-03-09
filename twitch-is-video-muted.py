#!/usr/bin/env python3
import os
import sys

from twitch.playlist import Playlist


def main():
    try:
        video_id = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.readline().strip()
        playlist = playlist_for(video_id)
        exit(0) if is_muted(playlist) else exit(1)
    except ValueError as error:
        sys.stderr.write(str(error) + os.linesep)
        exit(2)


def playlist_for(video_id):
    return Playlist().fetch_for_vod(video_id)


def is_muted(playlist):
    return any(map(lambda segment: segment.uri.endswith('muted.ts'), playlist.segments))


if __name__ == '__main__':
    main()
