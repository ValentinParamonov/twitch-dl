import itertools
import os
import re
import uuid
from collections import deque
from time import sleep

from twitch.constants import Twitch
from twitch.playlist import Playlist
from util.contents import Contents
from util.log import Log
from util.stopwatch import Stopwatch


class Recorder:
    def __init__(self):
        self.__recording = True
        self.__downloaded = deque(maxlen=32)
        self.__stopwatch = Stopwatch()
        self.__sleep_seconds = 10
        self.__file_name = uuid.uuid4().hex + '.ts'
        self.__stream_name = None
        self.__playlist = Playlist()

    def record(self, channel):
        while self.__recording:
            self.__stopwatch.split()
            segments = self.__fetch_segments(channel)
            if len(segments) == 0:
                if len(self.__downloaded) == 0:
                    Log.fatal('Seems like the channel is offline')
                break
            new_segments = self.__only_new(segments)
            self.__write(new_segments)
            self.__check_if_segments_lost(segments)
            self.__store_downloaded(new_segments)
            self.__adjust_sleep(len(segments) - len(new_segments))
            self.__rename_recording_if_stream_name_became_known_for(channel)
            time_to_sleep = self.__sleep_seconds - 2 * self.__stopwatch.split()
            if time_to_sleep > 0:
                sleep(time_to_sleep)
        Log.info('Broadcast ended.')

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

    def __fetch_segments(self, channel):
        playlist = self.__playlist.fetch_for_channel(channel)
        if playlist is None:
            return []
        segments = playlist.segments
        for segment in segments:
            segment.title = segment.uri.rsplit('/', 1)[1][:16]
        return segments

    def __only_new(self, segments):
        return list(filter(lambda s: s.title not in self.__downloaded, segments))

    def __check_if_segments_lost(self, segments):
        if len(self.__downloaded) == 0 or len(segments) == 0:
            return
        if segments[0].title not in self.__downloaded:
            Log.error('Lost segments detected!')
            Log.error("The first downloaded segment hasn't been seen before!")

    def __store_downloaded(self, new_segments):
        for segment in new_segments:
            self.__downloaded.append(segment.title)

    def __write(self, segments):
        with open(self.__file_name, 'ab') as file:
            for segment in segments:
                for chunk in Contents.chunked(segment.uri):
                    if chunk:
                        file.write(chunk)

    def __adjust_sleep(self, old_segment_count):
        if old_segment_count == 0:
            self.__sleep_seconds -= 0.5
        elif old_segment_count == 1:
            self.__sleep_seconds -= 0.3
        elif old_segment_count == 2:
            self.__sleep_seconds -= 0.1
        elif old_segment_count == 3:
            self.__sleep_seconds += 0.05
        elif old_segment_count == 4:
            self.__sleep_seconds += 0.1
        else:
            self.__sleep_seconds += 0.3

    def __rename_recording_if_stream_name_became_known_for(self, channel):
        if self.__stream_name:
            return
        self.__stream_name = self.__lookup_stream(channel)
        if self.__stream_name is None:
            return
        Log.info('Recording ' + self.__stream_name)
        old_file_name = self.__file_name
        self.__file_name = self.__next_vacant(self.__stream_name + '.ts')
        os.rename(old_file_name, self.__file_name)

    def stop(self):
        self.__recording = False
