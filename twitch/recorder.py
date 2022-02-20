import itertools
import pickle
import uuid
from collections import deque
from time import sleep

from twitch.constants import Twitch
from twitch.playlist import Playlist
from util.auth_header_provider import AuthHeaderProvider
from util.contents import Contents
from util.file import File
from util.log import Log
from util.stopwatch import Stopwatch


class Recorder:
    def __init__(self):
        self.__recording = True
        self.__downloaded = None
        self.__buffer_file_name = None
        self.__stopwatch = Stopwatch()
        self.__sleep_seconds = 5
        self.__file_name = uuid.uuid4().hex + '.ts'
        self.__stream_name = None
        self.__playlist = Playlist()

    def record(self, channel):
        consecutive_times_received_no_new_segments = 0
        notified_about_running_ad = False
        self.__init_segments_buffer(channel)
        while self.__recording:
            self.__stopwatch.split()
            ad_running, segments = self.__fetch_segments(channel)
            if not ad_running:
                if len(segments) == 0:
                    if len(self.__downloaded) == 0:
                        Log.fatal('Seems like the channel is offline')
                    break
                new_segments = self.__only_new(segments)
                if len(new_segments) != 0:
                    consecutive_times_received_no_new_segments = 0
                    self.__write(new_segments)
                    self.__check_if_segments_lost(segments)
                    self.__store_downloaded(new_segments)
                else:
                    consecutive_times_received_no_new_segments += 1
                    if consecutive_times_received_no_new_segments == 3:
                        break
                self.__rename_recording_if_stream_name_became_known_for(channel)
            elif not notified_about_running_ad:
                Log.info('Waiting for an ad to stop')
                notified_about_running_ad = True
            self.__sleep_if_needed()
        self.__store_segments_buffer()
        if self.__recording:
            Log.info('Broadcast ended.')
        else:
            Log.info('Stopped.')

    def __init_segments_buffer(self, channel_name):
        self.__buffer_file_name = f'{File.user_cache_dir()}/twitch-dl/{channel_name}.buff'
        self.__downloaded = self.__load_buffer_from_file(self.__buffer_file_name)

    @staticmethod
    def __load_buffer_from_file(file_name):
        if File.exists(file_name) and not File.age_in_seconds(file_name) > 60:
            with open(file_name, 'rb') as buffer_file:
                return pickle.load(buffer_file)
        return deque(maxlen=32)

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
    def __next_vacant(stream_name, extension):
        new_name = stream_name
        for i in itertools.count(1):
            if not File.isfile(new_name + extension):
                return new_name + extension
            new_name = f'{stream_name} {i:02}'

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
            self.__stream_name.strip().replace('/', ''),
            '.ts'
        )
        if File.exists(old_file_name):
            File.rename(old_file_name, self.__file_name)

    def __sleep_if_needed(self):
        time_to_sleep = self.__sleep_seconds - 2 * self.__stopwatch.split()
        if time_to_sleep > 0:
            sleep(time_to_sleep)

    def __store_segments_buffer(self):
        with open(self.__buffer_file_name, 'wb') as buffer_file:
            pickle.dump(self.__downloaded, buffer_file)

    def stop(self):
        self.__recording = False
