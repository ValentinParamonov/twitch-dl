import os
from sys import stderr, stdout, exit


class Log:
    @staticmethod
    def fatal(msg):
        Log.error(msg)
        exit(1)

    @staticmethod
    def info(msg):
        stdout.write(msg + os.linesep)
        stdout.flush()

    @staticmethod
    def error(msg):
        stderr.write(msg + os.linesep)
        stderr.flush()
