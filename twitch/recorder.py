import itertools
import os
import re
import uuid
from collections import deque
from time import sleep

from twitch.constants import Twitch
from twitch.playlist import Playlist
from util.auth_header_provider import AuthHeaderProvider
from util.contents import Contents
from util.log import Log
from util.stopwatch import Stopwatch


class Recorder:
    def __init__(self):
        self.__recording = True
        self.__downloaded = deque(maxlen=32)
        self.__stopwatch = Stopwatch()
        self.__sleep_seconds = 5
        self.__file_name = uuid.uuid4().hex + '.ts'
        self.__stream_name = None
        self.__playlist = Playlist()

    def record(self, channel):
        consecutive_times_received_no_new_segments = 0
        notified_about_running_ad = False
        while self.__recording:
            self.__stopwatch.split()
            ad_running, segments = self.__fetch_segments(channel)
            if not ad_running:
                if len(segments) == 0:
                    if len(self.__downloaded) == 0:
                        Log.fatal('Seems like the channel is offline')
                    break
                new_segments = self.__only_new(segments)
                if len(new_segments) == 0:
                    consecutive_times_received_no_new_segments += 1
                    if consecutive_times_received_no_new_segments == 3:
                        break
                else:
                    consecutive_times_received_no_new_segments = 0
                self.__write(new_segments)
                self.__check_if_segments_lost(segments)
                self.__store_downloaded(new_segments)
                self.__rename_recording_if_stream_name_became_known_for(channel)
            elif not notified_about_running_ad:
                Log.info('Waiting for an ad to stop')
                notified_about_running_ad = True
            self.__sleep_if_needed()
        if self.__recording:
            Log.info('Broadcast ended.')
        else:
            Log.info('Stopped.')

    @staticmethod
    def __lookup_stream_name(channel):
        response = Contents.json(
            Twitch.stream_link,
            params={'user_login': channel},
            headers=AuthHeaderProvider.authenticate(),
        )
        if response['data'] is None or len(response['data']) == 0:
            return None
        return response['data'][0]['title']

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
        segments = list(
            filter(lambda s: s.title == Twitch.stream_segment_title, playlist.segments))
        if len(playlist.segments) != 0 and len(segments) == 0:
            return True, []
        for segment in segments:
            # taking 10 characters before the common part at the end of the URL
            segment.title = segment.uri[-29:-19]
        return False, segments

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
                        try:
                            file.write(chunk)
                        except IOError as e:
                            Log.error(str(e))

    def __rename_recording_if_stream_name_became_known_for(self, channel):
        if self.__stream_name:
            return
        self.__stream_name = self.__lookup_stream_name(channel)
        if self.__stream_name is None:
            return
        Log.info('Recording ' + self.__stream_name)
        old_file_name = self.__file_name
        self.__file_name = self.__next_vacant(
            self.__stream_name.replace('/', '') + '.ts'
        )
        os.rename(old_file_name, self.__file_name)

    def __sleep_if_needed(self):
        time_to_sleep = self.__sleep_seconds - 2 * self.__stopwatch.split()
        if time_to_sleep > 0:
            sleep(time_to_sleep)

    def stop(self):
        self.__recording = False
