#!/usr/bin/env python3

import itertools
import os
import re
import signal
import sys
import uuid
from collections import deque
from time import time, sleep

from twitch.constants import Twitch
from twitch.playlist import Playlist
from util.contents import Contents


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
        self.downloaded = deque(maxlen=8)
        self.stopwatch = Stopwatch()
        self.sleep_seconds = 10
        self.file_name = uuid.uuid4().hex + '.ts'
        self.stream_name = None

    def record(self, channel):
        while self.recording:
            self.stopwatch.split()
            segments = self.__fetch_segments(channel)
            if len(segments) == 0:
                if len(self.downloaded) != 0:
                    print('Broadcast ended.')
                else:
                    print('Seems like the channel is offline')
                return
            new_segments = self.__only_new(segments)
            self.__write(new_segments)
            if self.__segments_lost(new_segments):
                sys.stderr.write('Lost segments detected!\n')
            self.__store_downloaded(new_segments)
            self.__adjust_sleep(len(segments) - len(new_segments))
            self.__rename_recording_if_stream_name_became_known_for(channel)
            time_to_sleep = self.sleep_seconds - 2 * self.stopwatch.split()
            if time_to_sleep > 0:
                sleep(time_to_sleep)

    @staticmethod
    def __lookup_stream(channel):
        response = Contents.json(
            Twitch.stream_link.format(channel),
            headers=Twitch.client_id_header
        )
        if response['stream'] is None:
            return None
        return response['stream']['channel']['status']

    @staticmethod
    def __next_vacant(file_name: str):
        new_name = file_name
        for i in itertools.count(1):
            if not os.path.isfile(new_name):
                return new_name
            new_name = re.sub(r'(\..+)$', r' {:02}\1'.format(i), file_name)

    @staticmethod
    def __fetch_segments(channel):
        playlist = Playlist.fetch_for_channel(channel)
        if playlist is None:
            return []
        segments = playlist.segments
        for segment in segments:
            segment.title = segment.uri.rsplit('/', 1)[1]
        return segments

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

    def __write(self, segments):
        with open(self.file_name, 'ab') as file:
            for segment in segments:
                for chunk in Contents.chunked(segment.uri):
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

    def __rename_recording_if_stream_name_became_known_for(self, channel):
        if self.stream_name:
            return
        self.stream_name = self.__lookup_stream(channel)
        if self.stream_name is None:
            return
        print('Recording ' + self.stream_name)
        old_file_name = self.file_name
        self.file_name = self.__next_vacant(self.stream_name + '.ts')
        os.rename(old_file_name, self.file_name)

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
