#!/usr/bin/env python3
import re
import sys
from collections import deque

import os

import itertools
import requests
import m3u8
from time import time, sleep
import signal


class Stopwatch:
    def __init__(self):
        self.last = time()

    def split(self):
        now = time()
        last = self.last
        self.last = now
        return now - last


class Recorder:
    def __init__(self):
        self.recording = True
        self.client_id = {'Client-ID': 'jzkbprff40iqj646a697cyrvl0zt2m6'}
        self.downloaded = deque(maxlen=8)
        self.stopwatch = Stopwatch()
        self.sleep_seconds = 10

    def record(self, channel):
        stream_name = self.__lookup_stream(channel)
        if stream_name is None:
            print('Seems like {} is offline'.format(channel))
            return
        file_name = self.__next_vacant(stream_name + '.ts')
        print('recording ' + stream_name)
        while self.recording:
            self.stopwatch.split()
            segments = self.__fetch_segments(channel)
            if len(segments) == 0:
                print('Broadcast ended.')
                return
            new_segments = self.__only_new(segments)
            self.__write(file_name, new_segments)
            if self.__segments_lost(new_segments):
                sys.stderr.write('Lost segments detected!\n')
            self.__store_downloaded(new_segments)
            self.__adjust_sleep(len(segments) - len(new_segments))
            time_to_sleep = self.sleep_seconds - 2 * self.stopwatch.split()
            if time_to_sleep > 0:
                sleep(time_to_sleep)

    def __lookup_stream(self, channel):
        response = requests.get(
            'https://api.twitch.tv/kraken/streams/{}'.format(channel),
            headers=self.client_id
        )
        if response.status_code != 200:
            return None
        json = response.json()
        if json['stream'] is None:
            return None
        return json['stream']['channel']['status']

    @staticmethod
    def __next_vacant(file_name: str):
        new_name = file_name
        for i in itertools.count(1):
            if not os.path.isfile(new_name):
                return new_name
            new_name = re.sub(r'(\..+)$', r' {:02}\1'.format(i), file_name)

    def __fetch_segments(self, channel):
        best_quality_link = self.__best_quality_link(channel)
        if best_quality_link is None:
            return []
        playlist = requests.get(best_quality_link).content.decode('utf-8')
        base_url = best_quality_link[0:best_quality_link.rfind('/')]
        segments = m3u8.loads(playlist).segments
        for segment in segments:
            segment.title = segment.uri
            segment.base_path = base_url
        return segments

    def __best_quality_link(self, channel):
        token = self.__fetch_token(channel)
        if token is None:
            return None
        playlist = self.__fetch_playlist(channel, token)
        if playlist is None:
            return None
        return next(filter(lambda line: 'http' in line, playlist.split('\n')))

    def __fetch_token(self, channel):
        response = requests.get(
            'https://api.twitch.tv/api/channels/{}/access_token'.format(channel),
            headers=self.client_id
        )
        if response.status_code != 200:
            return None
        return response.json()

    @staticmethod
    def __fetch_playlist(channel, token):
        response = requests.get(
            'https://usher.ttvnw.net/api/channel/hls/{}.m3u8'.format(channel),
            params={'token': token['token'], 'sig': token['sig']}
        )
        if response.status_code != 200:
            return None
        return response.content.decode('utf-8')

    def __only_new(self, segments):
        return list(filter(lambda s: s.title not in self.downloaded, segments))

    def __segments_lost(self, new_segments):
        return False if len(self.downloaded) == 0 else \
            self.__segment_index(new_segments[0].title) \
            != self.__segment_index(self.downloaded[-1]) + 1

    @staticmethod
    def __segment_index(segment_title):
        return int(segment_title.split('-')[1])

    def __store_downloaded(self, new_segments):
        for segment in new_segments:
            self.downloaded.append(segment.title)

    @staticmethod
    def __write(file_name, segments):
        with open(file_name, 'ab') as file:
            for segment in segments:
                chunks = requests.get(segment.uri)
                for chunk in chunks.iter_content(chunk_size=2048):
                    if chunk:
                        file.write(chunk)

    def __adjust_sleep(self, old_segment_count):
        if old_segment_count == 0:
            self.sleep_seconds -= 0.5
        elif old_segment_count == 1:
            self.sleep_seconds -= 0.05
        elif old_segment_count == 2:
            self.sleep_seconds += 0.1
        elif old_segment_count == 3:
            self.sleep_seconds += 0.3
        else:
            self.sleep_seconds += 0.5

    def stop(self):
        self.recording = False


if __name__ == '__main__':
    if (len(sys.argv)) != 2:
        sys.stderr.write('Needs channel to record!\n')
        sys.exit(1)
    channel_name = sys.argv[1]
    recorder = Recorder()
    signal.signal(signal.SIGINT, lambda sig, frame: recorder.stop())
    recorder.record(channel_name)
