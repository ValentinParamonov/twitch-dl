import os.path
import time


class File:
    @staticmethod
    def exists(file_name):
        return os.path.exists(file_name)

    @staticmethod
    def age_in_seconds(file_name):
        return time.time() - os.path.getmtime(file_name)

    @staticmethod
    def rename(old_file_name, new_file_name):
        os.rename(old_file_name, new_file_name)

    @staticmethod
    def isfile(file_name):
        return os.path.isfile(file_name)

    @staticmethod
    def user_cache_dir():
        cache_dir = os.environ.get('XDG_CACHE_HOME')
        if cache_dir:
            return cache_dir
        return os.path.expanduser('~/.cache')
