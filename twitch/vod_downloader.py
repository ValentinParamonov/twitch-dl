import asyncio

from twitch.progressbar import ProgressBar
from util.asynccontents import AsyncContents, ResponseError
from util.log import Log


class StoppedException(Exception):
    pass


class VodDownloader:
    BATCH_SIZE = 8

    def __init__(self, segments):
        self.segments = segments
        self.stopped = False

    async def download_to(self, file_name):
        progress_bar = ProgressBar(file_name, len(self.segments))
        try:
            async with AsyncContents():
                await self.download_file(file_name, progress_bar)
        except Exception as e:
            Log.fatal('\n' + str(e))

    async def download_file(self, file_name, progress_bar):
        last_offset = 0
        for batch in self.chunks_of_size(self.segments, self.BATCH_SIZE):
            if self.stopped:
                return
            segments_with_offsets, new_offset = await self.get_segment_offsets(batch, last_offset)
            last_offset = new_offset
            download_jobs = []
            for segment, offset in segments_with_offsets:
                download_jobs.append(self.fetch_segment_and_write(segment, offset, file_name, progress_bar))
            await self.wait_for(download_jobs)

    @staticmethod
    def chunks_of_size(segments, batch_size):
        return [segments[i:i + batch_size] for i in range(0, len(segments), batch_size)]

    @staticmethod
    async def wait_for(download_jobs):
        done, pending = await asyncio.wait(download_jobs, return_when=asyncio.FIRST_EXCEPTION)
        for job in pending:
            job.cancel()
        exception = None
        for job in done:
            exception = job.exception()
        if exception is not None:
            raise exception

    async def fetch_segment_and_write(self, segment, offset, file_name, progress_bar):
        chunks = await AsyncContents().chunked(segment)
        with open(file_name, 'rb+') as file:
            file.seek(offset)
            async for chunk in chunks:
                if self.stopped:
                    raise StoppedException('Stopped')
                file.write(chunk)
        progress_bar.update_by(1)

    @classmethod
    async def get_segment_offsets(cls, batch, initial_offset):
        segment_sizes = await asyncio.gather(*[cls.get_segment_size(segment) for segment in batch])
        segment_offsets = cls.build_offsets(segment_sizes, initial_offset)
        return zip(batch, segment_offsets), initial_offset + sum(segment_sizes)

    @classmethod
    async def get_segment_size(cls, segment):
        while True:
            try:
                headers = await AsyncContents().headers(segment)
                return int(headers['Content-Length'])
            except ResponseError as e:
                # sometimes HEAD request randomly fail with 'Bad Request'
                # just retry in such case
                if e.status_code == 400 and e.status_message == 'Bad Request':
                    continue
                else:
                    raise e

    @staticmethod
    def build_offsets(segment_sizes, initial_offset):
        for size in segment_sizes:
            yield initial_offset
            initial_offset += size

    def stop(self):
        self.stopped = True
