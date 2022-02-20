import os.path
import time


class File:
    @staticmethod
    def exists(file_name):
        return os.path.exists(file_name)

    @staticmethod
    def age_in_seconds(file_name):
        time.time() - os.path.getmtime(file_name)
