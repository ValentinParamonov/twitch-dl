#! /usr/bin/env python3

import os
import re
import sys
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from functools import reduce
from itertools import groupby
from optparse import OptionParser, OptionValueError
from sys import stderr, stdout, exit
from threading import Lock
from urllib.parse import urlparse, parse_qs

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
    def __init__(self, name, size, offset, duration, start):
        self.name = name
        self.size = size
        self.offset = offset
        self.duration = duration
        self.start = start


class Playlist:
    def __init__(self, chunks, totalBytes, totalDuration, baseUrl):
        self.chunks = chunks
        self.totalBytes = totalBytes
        self.totalDuration = totalDuration
        self.baseUrl = baseUrl

    @staticmethod
    def get(link, startTime, endTime):
        playlist = Contents.utf8(link)
        (chunks, totalBytes, totalDuration) = Chunks.get(playlist, startTime, endTime)
        baseUrl = link.rsplit('/', 1)[0]
        return Playlist(chunks, totalBytes, totalDuration, baseUrl)


class Chunks:
    @classmethod
    def get(cls, playlist, startTime, endTime):
        # min endTIme totalDuration
        return cls.withFileOffsets(cls.chunksWithOffsets(playlist))

    @staticmethod
    def withFileOffsets(chunksWithOffsets):
        fileOffset = 0
        totalDuration = 0
        chunks = []
        for chunkName, (size, duration) in chunksWithOffsets.items():
            chunks.append(Chunk(chunkName, size, fileOffset, duration, totalDuration))
            fileOffset += size + 1
            totalDuration += duration
        return (chunks, fileOffset, totalDuration)

    @classmethod
    def chunksWithOffsets(cls, vodLinks):
        playlist = m3u8.loads(vodLinks)
        chunksWithEndOffsets = map(cls.toChunk, playlist.segments)
        return cls.toUberChunks(groupby(chunksWithEndOffsets, lambda c: c[0]))

    @staticmethod
    def toChunk(segment):
        parsedLink = urlparse(segment.uri)
        chunkName = parsedLink.path
        endOffset = parse_qs(parsedLink.query)['end_offset'][0]
        return (chunkName, int(endOffset), segment.duration)

    @staticmethod
    def toUberChunks(groupedByName):
        uberChunks = OrderedDict()
        for chunkName, chunkGroup in groupedByName:
            chunks = list(chunkGroup)
            uberChunkSize = chunks[-1][1]
            uberChunkDuration = reduce(lambda total, chunk: total + chunk[2], chunks, 0)
            uberChunks[chunkName] = (uberChunkSize, uberChunkDuration)
        return uberChunks


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
        self.printBar(percentCompleted)
        self.lock.release()

    def printBar(self, percentCompleted):
        Log.info('\r' + ' ' * self.getConsoleWidth())
        Log.info('\r{file} [{percents:3.0f}%]{terminator}'.format(
            file=self.fileName,
            percents=percentCompleted,
            terminator='\n' if self.current == self.total else ''))

    def getConsoleWidth(self):
        _, width = os.popen('stty size', 'r').read().split()
        return int(width)


class CommandLineParser:
    timePattern = '^(((?P<h>0{1,2}|[1-9]\d*):)?((?P<m>[0-5]?[0-9]):))?(?P<s>[0-5]?[0-9])$'

    def __init__(self):
        parser = OptionParser()
        parser.add_option('-s', '--start_time', metavar='START', action='callback', callback=self.toSeconds, type='string', default=0)
        parser.add_option('-e', '--end_time', metavar='END', action='callback', callback=self.toSeconds, type='string', default=sys.maxsize)
        parser.usage = '%prog [options] vod_id'
        self.getUsage = lambda: parser.get_usage()
        self.parseArgs = lambda: parser.parse_args()

    def toSeconds(self, option, optString, timeString, parser):
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

    def links(self):
        token = self.accessTokenFor(self.vodId)
        recodedToken = {'nauth': token['token'], 'nauthsig': token['sig']}
        return Contents.utf8('http://usher.justin.tv/vod/{}'.format(self.vodId), params=recodedToken)

    def accessTokenFor(self, vodId):
        return Contents.json('https://api.twitch.tv/api/vods/{}/access_token'.format(vodId))

    def name(self):
        return Contents.json('https://api.twitch.tv/kraken/videos/v{}'.format(self.vodId))['title']

    def sourceQualityLink(self):
        links = self.links().split('\n')
        return next(filter(lambda line: '/high/' in line, links)).replace('/high/', '/chunked/')


class FileMaker:
    @classmethod
    def makeAvoidingOverwrite(cls, desiredName):
        actualName = cls.findUntaken(desiredName)
        open(actualName, 'w').close()
        return actualName

    @staticmethod
    def findUntaken(desiredName):
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
                whenDone = lambda chunk: self.onChunkProcessed(chunk, progressBar)
                executor.submit(self.downloadChunkAndWriteToFile, chunk, fileName, playlist.baseUrl).add_done_callback(whenDone)

    def downloadChunkAndWriteToFile(self, chunk, fileName, baseUrl):
        chunkContents = Contents.raw('{base}/{chunk}?start_offset=0&end_offset={end}'.format(base=baseUrl, chunk=chunk.name, end=chunk.size)).content
        return self.writeContents(chunkContents, fileName, chunk.offset)

    def writeContents(self, chunkContents, fileName, offset):
        with open(fileName, 'rb+') as file:
            file.seek(offset)
            bytesWritten = file.write(chunkContents)
            return bytesWritten

    def onChunkProcessed(self, chunk, progressBar):
        if chunk.exception():
            Log.error(str(chunk.exception()))
        progressBar.updateBy(chunk.result())


class Contents:
    @classmethod
    def utf8(cls, resource, params=None):
        return cls.raw(resource, params).decode('utf-8')

    @classmethod
    def raw(cls, resource, params=None):
        return cls.getOk(resource, params).content

    @classmethod
    def json(cls, resource, params=None):
        return cls.getOk(resource, params).json()

    @classmethod
    def getOk(cls, resource, params=None):
        return cls.checkOk(cls.get(resource, params))

    @staticmethod
    def get(resource, params=None):
        try:
            return requests.get(resource, params=params)
        except Exception as e:
            Log.error(str(e))

    @staticmethod
    def checkOk(response):
        if response.status_code != status.ok:
            Log.error('Failed to get {url}: got {statusCode} response'.format(url=response.url, statusCode=response.status_code))
        return response


def main():
    (startTime, endTime, vodId) = CommandLineParser().parseCommandLine()
    vod = Vod(vodId)
    playlist = Playlist.get(vod.sourceQualityLink(), startTime, endTime)
    fileName = FileMaker.makeAvoidingOverwrite(vod.name() + '.ts')
    PlaylistDownloader(playlist).downloadTo(fileName)


if __name__ == '__main__':
    main()
