#! /usr/bin/env python3

import os
import re
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from optparse import OptionParser
from sys import stdout, stderr
from threading import Lock
from urllib.parse import urlparse, parse_qs

import m3u8
import requests
from requests import codes as status


class Chunk:
    def __init__(self, name, duration, localOffset, fileOffset):
        self.name = name
        self.duration = duration
        self.localOffset = localOffset
        self.fileOffset = fileOffset


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
        info('\r' + ' ' * self.getConsoleWidth())
        info('\r{file} [{percents:3.0f}%]{terminator}'.format(
            file=self.fileName,
            percents=percentCompleted,
            terminator='\n' if self.current == self.total else ''))

    def getConsoleWidth(self):
        _, width = os.popen('stty size', 'r').read().split()
        return int(width)


progressBar = None


def main():
    global progressBar
    vodId = vodIdFromArgs()
    fileName = createFile(vodName(vodId) + '.ts')
    sourceQualityLink = sourceQualityLinkIn(playlistsFor(vodId))
    (chunks, totalBytes, totalDuration) = withFileOffsets(chunksWithOffsets(contentsOf(sourceQualityLink)))
    baseUrl = sourceQualityLink.rsplit('/', 1)[0]
    progressBar = ProgressBar(fileName, totalBytes)
    downLoadFileFromChunks(fileName, chunks, baseUrl)


def vodIdFromArgs():
    parser = OptionParser()
    (_, args) = parser.parse_args()
    parser.usage = '%prog vod_id'
    argCount = len(args)
    if argCount != 1:
        parser.print_usage()
        exit(1)
    try:
        return int(args[0])
    except ValueError:
        parser.print_usage()
        exit(1)


def playlistsFor(vodId):
    token = accessTokenFor(vodId)
    recodedToken = {'nauth': token['token'], 'nauthsig': token['sig']}
    res = requests.get('http://usher.justin.tv/vod/{}'.format(vodId), params=recodedToken)
    return checkOk(res).content.decode('utf-8')


def accessTokenFor(vodId):
    return jsonOf('https://api.twitch.tv/api/vods/{}/access_token'.format(vodId))


def sourceQualityLinkIn(playlist):
    return next(filter(lambda line: '/high/' in line, playlist.split('\n'))).replace('/high/', '/chunked/')


def checkOk(response):
    if response.status_code != status.ok:
        error('Failed to get {url}: got {statusCode} response'.format(url=response.url, statusCode=response.status_code))
    return response


def error(msg):
    stderr.write(msg)
    exit(1)


def info(msg):
    stdout.write(msg)
    stdout.flush()


def contentsOf(resource):
    return rawContentsOf(resource).decode('utf-8')


def rawContentsOf(resource):
    return checkOk(getFrom(resource)).content


def getFrom(resource):
    try:
        return requests.get(resource)
    except ConnectionError as ce:
        error(str(ce))


def chunksWithOffsets(vodLinks):
    playlist = m3u8.loads(vodLinks)
    chunksWithEndOffsets = map(parseSegment, playlist.segments)
    return OrderedDict(chunksWithEndOffsets)


def parseSegment(segment):
    parsedLink = urlparse(segment.uri)
    chunkName = parsedLink.path
    endOffset = parse_qs(parsedLink.query)['end_offset'][0]
    return (chunkName, (segment.duration, endOffset))


def vodName(vodId):
    return jsonOf('https://api.twitch.tv/kraken/videos/v{}'.format(vodId))['title']


def jsonOf(resource):
    return checkOk(getFrom(resource)).json()


def withFileOffsets(chunksWithOffsets):
    fileOffset = 0
    totalDuration = 0
    chunks = []
    for chunk, (duration, offset) in chunksWithOffsets.items():
        chunks.append(Chunk(chunk, duration, offset, fileOffset))
        fileOffset += int(offset) + 1
        totalDuration += float(duration)
    return (chunks, fileOffset, totalDuration)


def downLoadFileFromChunks(fileName, chunks, baseUrl):
    with ThreadPoolExecutor(max_workers=10) as executor:
        for chunk in chunks:
            executor.submit(downloadChunkAndWriteToFile, chunk, fileName, baseUrl).add_done_callback(onChunkProcessed)


def createFile(initialName):
    actualName = findSuitable(initialName)
    open(actualName, 'w').close()
    return actualName


def findSuitable(fileName):
    modifier = 0
    newName = fileName
    while os.path.isfile(newName):
        modifier += 1
        newName = re.sub(r'.ts$', ' {:02}.ts'.format(modifier), fileName)
    return fileName if modifier == 0 else newName


def downloadChunkAndWriteToFile(chunk, fileName, baseUrl):
    chunkContents = rawContentsOf('{base}/{chunk}?start_offset=0&end_offset={end}'.format(base=baseUrl, chunk=chunk.name, end=chunk.localOffset))
    return writeContents(chunkContents, fileName, chunk.fileOffset)


def writeContents(chunkContents, fileName, offset):
    with open(fileName, 'rb+') as file:
        file.seek(offset)
        bytesWritten = file.write(chunkContents)
        return bytesWritten


def onChunkProcessed(chunk):
    if chunk.exception():
        error(str(chunk.exception()))
    progressBar.updateBy(chunk.result())


if __name__ == '__main__':
    main()
