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
    def __init__(self, url, fileOffset):
        self.url = url
        self.fileOffset = fileOffset


class Playlist:
    def __init__(self, chunks, totalBytes):
        self.chunks = chunks
        self.totalBytes = totalBytes


class PlaylistBuilder:
    @classmethod
    def __baseUrl(cls, link):
        baseUrl = link.rsplit('/', 1)[0]
        return baseUrl[0:baseUrl.rfind('/')] + '/chunked'

    @classmethod
    def get(cls, link, startTime, endTime):
        segments = m3u8.loads(Contents.utf8(link)).segments
        baseUrl = cls.__baseUrl(link)
        for segment in segments:
            segment.base_path = baseUrl
        (chunks, totalBytes) = Chunks.get(segments, startTime, endTime)
        return Playlist(chunks, totalBytes)


class Chunks:
    @classmethod
    def get(cls, segments, startTime, endTime):
        clippedSegments = cls.__clipped(cls.__withTime(segments), startTime, endTime)
        return cls.__toChunks(cls.__withLength(clippedSegments))

    @staticmethod
    def __withTime(segments):
        start = 0
        withTime = []
        for segment in segments:
            withTime.append((start, segment))
            start += segment.duration
        return withTime

    @staticmethod
    def __clipped(segments, startTime, endTime):
        return [s for (start, s) in segments if (start + s.duration) > startTime and start < endTime]

    @classmethod
    def __withLength(cls, segments):
        return map(lambda s: (s, cls.__queryChunkSize(s.uri)), segments)

    @staticmethod
    def __queryChunkSize(chunkUri):
        return int(Contents.__headers(chunkUri)['content-length'])

    @staticmethod
    def __toChunks(segmentsWithLength):
        fileOffset = 0
        chunks = []
        for segment, length in segmentsWithLength:
            chunks.append(Chunk(segment.uri, fileOffset))
            fileOffset += length
        totalSize = fileOffset
        return (chunks, totalSize)


class ProgressBar:
    def __init__(self, fileName, fileSize):
        self.fileName = fileName
        self.total = fileSize
        self.current = 0
        self.lock = Lock()
        self.updateBy(0)

    def updateBy(self, bytes):
        self.lock.acquire()
        self.current += bytes
        percentCompleted = self.current / self.total * 100
        self.__printBar(percentCompleted)
        self.lock.release()

    def __printBar(self, percentCompleted):
        Log.info('\r' + ' ' * self.__getConsoleWidth())
        Log.info('\r{file} [{percents:3.0f}%]{terminator}'.format(
            file=self.fileName,
            percents=percentCompleted,
            terminator='\n' if self.current == self.total else ''))

    def __getConsoleWidth(self):
        _, width = os.popen('stty size', 'r').read().split()
        return int(width)


class CommandLineParser:
    timePattern = '^(((?P<h>0{1,2}|[1-9]\d*):)?((?P<m>[0-5]?[0-9]):))?(?P<s>[0-5]?[0-9])$'

    def __init__(self):
        parser = OptionParser()
        parser.add_option('-s', '--start_time', metavar='START', action='callback', callback=self.__toSeconds, type='string', default=0)
        parser.add_option('-e', '--end_time', metavar='END', action='callback', callback=self.__toSeconds, type='string', default=sys.maxsize)
        parser.usage = '%prog [options] vod_id'
        self.getUsage = lambda: parser.get_usage()
        self.parseArgs = lambda: parser.parse_args()

    def __toSeconds(self, option, optString, timeString, parser):
        match = re.search(self.timePattern, timeString)
        if not match:
            raise OptionValueError('Invalid time format for option {}'.format(option.dest))
        ts = dict(map(lambda g: (g, int(match.group(g) or '0')), ['h', 'm', 's']))
        seconds = ts['h'] * 3600 + ts['m'] * 60 + ts['s']
        setattr(parser.values, option.dest, seconds)

    def parseCommandLine(self):
        (options, args) = self.parseArgs()
        if len(args) != 1:
            Log.error(self.getUsage())
        if options.end_time <= options.start_time:
            Log.error("End time can't be earlier than start time\n")
        try:
            return (options.start_time, options.end_time, int(args[0]))
        except ValueError:
            Log.error(self.getUsage())


class Vod:
    def __init__(self, vodId):
        self.vodId = vodId

    def highestQualityLink(self):
        links = self.__links().split('\n')
        return next(filter(lambda line: 'http' in line, links))

    def __links(self):
        token = self.__accessTokenFor(self.vodId)
        recodedToken = {'nauth': token['token'], 'nauthsig': token['sig']}
        return Contents.utf8('http://usher.justin.tv/vod/{}'.format(self.vodId), params=recodedToken)

    def __accessTokenFor(self, vodId):
        return Contents.json('https://api.twitch.tv/api/vods/{}/access_token'.format(vodId))

    def name(self):
        return Contents.json('https://api.twitch.tv/kraken/videos/v{}'.format(self.vodId))['title']


class FileMaker:
    @classmethod
    def makeAvoidingOverwrite(cls, desiredName):
        actualName = cls.__findUntaken(desiredName)
        open(actualName, 'w').close()
        return actualName

    @staticmethod
    def __findUntaken(desiredName):
        modifier = 0
        newName = desiredName
        while os.path.isfile(newName):
            modifier += 1
            newName = re.sub(r'.ts$', ' {:02}.ts'.format(modifier), desiredName)
        return desiredName if modifier == 0 else newName


class PlaylistDownloader:
    def __init__(self, playlist):
        self.playlist = playlist

    def downloadTo(self, fileName):
        playlist = self.playlist
        progressBar = ProgressBar(fileName, playlist.totalBytes)
        with ThreadPoolExecutor(max_workers=10) as executor:
            for chunk in playlist.chunks:
                whenDone = lambda chunk: self.__onChunkProcessed(chunk, progressBar)
                executor.submit(self.__downloadChunkAndWriteToFile, chunk, fileName).add_done_callback(whenDone)

    def __downloadChunkAndWriteToFile(self, chunk, fileName):
        chunkContents = Contents.raw(chunk.url)
        return self.__writeContents(chunkContents, fileName, chunk.fileOffset)

    def __writeContents(self, chunkContents, fileName, offset):
        with open(fileName, 'rb+') as file:
            file.seek(offset)
            bytesWritten = file.write(chunkContents)
            return bytesWritten

    def __onChunkProcessed(self, chunk, progressBar):
        if chunk.exception():
            Log.error(str(chunk.exception()))
        progressBar.updateBy(chunk.result())


class Contents:
    @classmethod
    def utf8(cls, resource, params=None):
        return cls.raw(resource, params).decode('utf-8')

    @classmethod
    def raw(cls, resource, params=None):
        return cls.__getOk(resource, params).content

    @classmethod
    def json(cls, resource, params=None):
        return cls.__getOk(resource, params).json()

    @classmethod
    def __getOk(cls, resource, params=None):
        return cls.__checkOk(cls.__get(resource, params))

    @classmethod
    def __headers(cls, resource):
        try:
            return cls.__checkOk(requests.head(resource)).headers
        except Exception as e:
            Log.error(str(e))

    @staticmethod
    def __get(resource, params=None):
        try:
            twitch_web_player_client_id = {'Client-ID': 'jzkbprff40iqj646a697cyrvl0zt2m6'}
            return requests.get(resource, params=params, headers=twitch_web_player_client_id)
        except Exception as e:
            Log.error(str(e))

    @staticmethod
    def __checkOk(response):
        if response.status_code != status.ok:
            Log.error('Failed to get {url}: got {statusCode} response'.format(url=response.url, statusCode=response.status_code))
        return response


def main():
    (startTime, endTime, vodId) = CommandLineParser().parseCommandLine()
    vod = Vod(vodId)
    playlist = PlaylistBuilder.get(vod.highestQualityLink(), startTime, endTime)
    if playlist.totalBytes == 0:
        Log.error('Nothing to download\n')
    fileName = FileMaker.makeAvoidingOverwrite(vod.name() + '.ts')
    PlaylistDownloader(playlist).downloadTo(fileName)


if __name__ == '__main__':
    main()
