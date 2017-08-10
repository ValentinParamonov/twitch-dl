#!/usr/bin/env python3

import sys
from collections import deque
import requests
import m3u8
from time import time, sleep


class Stopwatch:
    def __init__(self):
        self.last = time()

    def split(self):
        now = time()
        last = self.last
        self.last = now
        return now - last


def record(channel):
    downloaded = deque(maxlen=8)
    sleep_seconds = 10
    stopwatch = Stopwatch()
    while True:
        stopwatch.split()
        segments = fetch_segments(channel)
        new_segments = list(filter(lambda s: s.title not in downloaded, segments))
        write(new_segments)
        if segments_lost(downloaded, new_segments):
            sys.stderr.write('Lost segments detected!\n')
        for segment in new_segments:
            print(segment.title)
            downloaded.append(segment.title)
        sleep_seconds = adjust_sleep(
            sleep_seconds,
            len(segments) - len(new_segments)
        )
        time_to_sleep = sleep_seconds - 2 * stopwatch.split()
        if time_to_sleep > 0:
            sleep(time_to_sleep)


def fetch_segments(channel):
    token = requests.get(
        'https://api.twitch.tv/api/channels/{}/access_token'.format(channel),
        headers={'Client-ID': 'jzkbprff40iqj646a697cyrvl0zt2m6'}
    ).json()

    playlist = requests.get(
        'https://usher.ttvnw.net/api/channel/hls/{}.m3u8'.format(channel),
        params={'token': token['token'], 'sig': token['sig']}
    ).content.decode('utf-8')

    best_quality_link = next(
        filter(lambda line: 'http' in line, playlist.split('\n'))
    )

    playlist = requests.get(best_quality_link).content.decode('utf-8')

    base_url = best_quality_link[0:best_quality_link.rfind('/')]
    segments = m3u8.loads(playlist).segments

    for segment in segments:
        segment.title = segment.uri
        segment.base_path = base_url

    return segments


def segments_lost(downloaded, new_segments):
    return False if len(downloaded) == 0 else \
        segment_index(new_segments[0].title) != segment_index(downloaded[-1]) + 1


def segment_index(segment_title):
    return int(segment_title.split('-')[1])


def write(segments):
    with open('out.ts', 'ab') as file:
        for segment in segments:
            for chunk in requests.get(segment.uri).iter_content(chunk_size=2048):
                if chunk:
                    file.write(chunk)


def adjust_sleep(current_sleep, old_segment_count):
    if old_segment_count == 0:
        return current_sleep - 0.5
    elif old_segment_count == 1:
        return current_sleep - 0.05
    elif old_segment_count == 2:
        return current_sleep + 0.1
    elif old_segment_count == 3:
        return current_sleep + 0.3
    else:
        return current_sleep + 0.5


if __name__ == '__main__':
    if (len(sys.argv)) != 2:
        sys.stderr.write('Needs channel to record!\n')
        sys.exit(1)
    channel = sys.argv[1]
    record(channel)
