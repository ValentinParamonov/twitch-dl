#!/usr/bin/env python3

import signal
import sys

from twitch.recorder import Recorder
from util.log import Log


def main():
    if (len(sys.argv)) != 2:
        Log.fatal('Needs channel to record!\n')
    channel_name = sys.argv[1]
    recorder = Recorder()
    signal.signal(signal.SIGINT, lambda sig, frame: recorder.stop())
    recorder.record(channel_name)


if __name__ == '__main__':
    main()
