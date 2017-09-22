#!/usr/bin/env python3
import sys

from twitch.playlist import Playlist

if (len(sys.argv)) != 2:
    sys.stderr.write('No channel name given!\n')
    sys.exit(1)
channel_name = sys.argv[1]
playlist = Playlist.fetch_for_channel(channel_name)
if playlist is None:
    sys.exit(1)

