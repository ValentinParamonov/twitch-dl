#! /usr/bin/env python3

import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from optparse import OptionParser, OptionValueError
from sys import stderr, stdout, exit
from threading import Lock

import m3u8
import requests
from requests import codes as status


class Log:
    @staticmethod
    def error(msg):
        stderr.write(msg)
        exit(1)

    @staticmethod
    def info(msg):
        stdout.write(msg)
        stdout.flush()


class Chunk:
    def __init__(self, url, file_offset):
        self.url = url
        self.file_offset = file_offset


class Playlist:
    def __init__(self, chunks, total_bytes):
        self.chunks = chunks
        self.total_bytes = total_bytes


class PlaylistBuilder:
    @classmethod
    def __base_url(cls, link):
        base_url = link.rsplit('/', 1)[0]
        return base_url[0:base_url.rfind('/')] + '/chunked'

    @classmethod
    def get(cls, link, start_time, end_time):
        segments = m3u8.loads(Contents.utf8(link)).segments
        base_url = cls.__base_url(link)
        for segment in segments:
            segment.base_path = base_url
        (chunks, total_bytes) = Chunks.get(segments, start_time, end_time)
        return Playlist(chunks, total_bytes)


class Chunks:
    @classmethod
    def get(cls, segments, start_time, end_time):
        clipped_segments = cls.__clipped(
            cls.__with_time(segments),
            start_time,
            end_time
        )
        return cls.__to_chunks(cls.__with_length(clipped_segments))

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

    @classmethod
    def __with_length(cls, segments):
        return map(lambda s: (s, cls.__query_chunk_size(s.uri)), segments)

    @staticmethod
    def __query_chunk_size(chunk_uri):
        return int(Contents.headers(chunk_uri)['content-length'])

    @staticmethod
    def __to_chunks(segments_with_length):
        file_offset = 0
        chunks = []
        for segment, length in segments_with_length:
            chunks.append(Chunk(segment.uri, file_offset))
            file_offset += length
        total_size = file_offset
        return chunks, total_size


class ProgressBar:
    def __init__(self, file_name, file_size):
        self.fileName = file_name
        self.total = file_size
        self.current = 0
        self.lock = Lock()
        self.update_by(0)

    def update_by(self, byte_count):
        self.lock.acquire()
        self.current += byte_count
        percent_completed = self.current / self.total * 100
        self.__print_bar(percent_completed)
        self.lock.release()

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
            Log.error(self.get_usage())
        if options.end_time <= options.start_time:
            Log.error("End time can't be earlier than start time\n")
        try:
            return options.start_time, options.end_time, int(args[0])
        except ValueError:
            Log.error(self.get_usage())


class Vod:
    def __init__(self, vodId):
        self.vod_id = vodId

    def best_quality_link(self):
        links = self.__links().split('\n')
        return next(filter(lambda line: 'http' in line, links))

    def __links(self):
        token = self.__access_token_for(self.vod_id)
        recoded_token = {'nauth': token['token'], 'nauthsig': token['sig']}
        return Contents.utf8(
            'http://usher.justin.tv/vod/{}'.format(self.vod_id),
            params=recoded_token
        )

    @staticmethod
    def __access_token_for(vod_id):
        return Contents.json(
            'https://api.twitch.tv/api/vods/{}/access_token'.format(vod_id)
        )

    def name(self):
        return Contents.json(
            'https://api.twitch.tv/kraken/videos/v{}'.format(self.vod_id)
        )['title']


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

    def download_to(self, file_name):
        playlist = self.playlist
        progress_bar = ProgressBar(file_name, playlist.total_bytes)
        with ThreadPoolExecutor(max_workers=10) as executor:
            for chunk in playlist.chunks:
                executor.submit(
                    self.__download_chunk_and_write_to_file,
                    chunk,
                    file_name
                ).add_done_callback(self.__when_done(progress_bar))

    def __when_done(self, progress_bar):
        return lambda chunk: self.__on_chunk_processed(chunk, progress_bar)

    def __download_chunk_and_write_to_file(self, chunk: Chunk, file_name):
        chunk_contents = Contents.chunked(chunk.url)
        return self.__write_contents(chunk_contents, file_name, chunk.file_offset)

    @staticmethod
    def __write_contents(chunk_contents, file_name, offset):
        with open(file_name, 'rb+') as file:
            file.seek(offset)
            bytes_written = 0
            for chunk in chunk_contents.iter_content(chunk_size=2048):
                if chunk:
                    bytes_written += file.write(chunk)
            return bytes_written

    @staticmethod
    def __on_chunk_processed(chunk, progress_bar):
        if chunk.exception():
            Log.error(str(chunk.exception()))
        progress_bar.update_by(chunk.result())


class Contents:
    @classmethod
    def utf8(cls, resource, params=None):
        return cls.raw(resource, params).decode('utf-8')

    @classmethod
    def raw(cls, resource, params=None):
        return cls.__get_ok(resource, params).content

    @classmethod
    def json(cls, resource, params=None):
        return cls.__get_ok(resource, params).json()

    @classmethod
    def __get_ok(cls, resource, params=None):
        return cls.__check_ok(cls.__get(resource, params))

    @classmethod
    def headers(cls, resource):
        try:
            return cls.__check_ok(requests.head(resource)).headers
        except Exception as e:
            Log.error(str(e))

    @staticmethod
    def __get(resource, params=None):
        try:
            twitch_web_player_client_id = {
                'Client-ID': 'jzkbprff40iqj646a697cyrvl0zt2m6'
            }
            return requests.get(
                resource,
                params=params,
                headers=twitch_web_player_client_id,
                stream=True
            )
        except Exception as e:
            Log.error(str(e))

    @staticmethod
    def __check_ok(response):
        if response.status_code != status.ok:
            Log.error(
                'Failed to get {url}: got {statusCode} response'.format(
                    url=response.url,
                    statusCode=response.status_code
                )
            )
        return response

    @classmethod
    def chunked(cls, resource):
        return cls.__get_ok(resource)


def main():
    (start_time, end_time, vod_id) = CommandLineParser().parse_command_line()
    vod = Vod(vod_id)
    playlist = PlaylistBuilder.get(vod.best_quality_link(), start_time, end_time)
    if playlist.total_bytes == 0:
        Log.error('Nothing to download\n')
    file_name = FileMaker.make_avoiding_overwrite(vod.name() + '.ts')
    PlaylistDownloader(playlist).download_to(file_name)


if __name__ == '__main__':
    main()
