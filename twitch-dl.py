#! /usr/bin/env python3

import os
import re
import signal
import sys
from optparse import OptionParser, OptionValueError

from twitch.playlist import Playlist as PlaylistFetcher
from twitch.vod import Vod
from util.contents import Contents
from util.log import Log


class Playlist:
    def __init__(self, segments):
        self.segments = segments


class Chunks:
    @classmethod
    def get(cls, segments, start_time, end_time):
        clipped_segments = cls.__clipped(
            cls.__with_time(segments),
            start_time,
            end_time
        )
        return Playlist(list(map(lambda segment: segment.uri, clipped_segments)))

    @staticmethod
    def __with_time(segments):
        start = 0
        with_time = []
        for segment in segments:
            with_time.append((start, segment))
            start += segment.duration
        return with_time

    @staticmethod
    def __clipped(segments, start_time, end_time):
        return [
            s for (start, s)
            in segments
            if (start + s.duration) > start_time and start < end_time
        ]


class ProgressBar:
    def __init__(self, file_name, total_segments):
        self.fileName = file_name
        self.total = total_segments
        self.current = 0
        self.update_by(0)

    def update_by(self, count):
        self.current += count
        percent_completed = self.current / self.total * 100
        self.__print_bar(percent_completed)

    def __print_bar(self, percent_completed):
        Log.info('\r' + ' ' * self.__get_console_width())
        Log.info('\r{file} [{percents:3.0f}%]{terminator}'.format(
            file=self.fileName,
            percents=percent_completed,
            terminator='\n' if self.current == self.total else ''))

    @staticmethod
    def __get_console_width():
        _, width = os.popen('stty size', 'r').read().split()
        return int(width)


class CommandLineParser:
    time_pattern = \
        '^(((?P<h>0{1,2}|[1-9]\d*):)?((?P<m>[0-5]?[0-9]):))?(?P<s>[0-5]?[0-9])$'

    def __init__(self):
        parser = OptionParser()
        parser.add_option('-s', '--start_time', metavar='START', action='callback',
                          callback=self.__to_seconds, type='string', default=0)
        parser.add_option('-e', '--end_time', metavar='END', action='callback',
                          callback=self.__to_seconds, type='string',
                          default=sys.maxsize)
        parser.usage = '%prog [options] vod_id'
        self.get_usage = lambda: parser.get_usage()
        self.parse_args = lambda: parser.parse_args()

    def __to_seconds(self, option, opt_string, time_string, parser):
        match = re.search(self.time_pattern, time_string)
        if not match:
            raise OptionValueError(
                'Invalid time format for option {}'.format(option.dest)
            )
        ts = dict(map(lambda g: (g, int(match.group(g) or '0')), ['h', 'm', 's']))
        seconds = ts['h'] * 3600 + ts['m'] * 60 + ts['s']
        setattr(parser.values, option.dest, seconds)

    def parse_command_line(self):
        (options, args) = self.parse_args()
        if len(args) != 1:
            Log.fatal(self.get_usage())
        if options.end_time <= options.start_time:
            Log.fatal("End time can't be earlier than start time\n")
        try:
            return options.start_time, options.end_time, int(args[0])
        except ValueError:
            Log.fatal(self.get_usage())


class FileMaker:
    @classmethod
    def make_avoiding_overwrite(cls, desired_name):
        actual_name = cls.__find_vacant(desired_name)
        open(actual_name, 'w').close()
        return actual_name

    @staticmethod
    def __find_vacant(desired_name):
        modifier = 0
        new_name = desired_name
        while os.path.isfile(new_name):
            modifier += 1
            new_name = re.sub(r'.ts$', ' {:02}.ts'.format(modifier), desired_name)
        return desired_name if modifier == 0 else new_name


class PlaylistDownloader:
    def __init__(self, playlist: Playlist):
        self.playlist = playlist
        self.stopped = False

    def download_to(self, file_name):
        playlist = self.playlist
        progress_bar = ProgressBar(file_name, len(playlist.segments))
        with open(file_name, 'wb+') as file:
            for segment in playlist.segments:
                if self.stopped:
                    print('')
                    break
                for chunk in Contents.chunked(segment):
                    if chunk:
                        file.write(chunk)
                progress_bar.update_by(1)

    def stop(self):
        self.stopped = True


def main():
    (start_time, end_time, vod_id) = CommandLineParser().parse_command_line()
    m3u8_playlist = PlaylistFetcher().fetch_for_vod(vod_id)
    if m3u8_playlist is None:
        Log.fatal("Seems like vod {} doesn't exist".format(vod_id))
    playlist = Chunks.get(m3u8_playlist.segments, start_time, end_time)
    file_name = FileMaker.make_avoiding_overwrite(Vod.title(vod_id) + '.ts')
    downloader = PlaylistDownloader(playlist)
    signal.signal(signal.SIGINT, lambda sig, frame: downloader.stop())
    downloader.download_to(file_name)


if __name__ == '__main__':
    main()
