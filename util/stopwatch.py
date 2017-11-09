from time import time


class Stopwatch:
    def __init__(self):
        self.last = time()

    def split(self):
        now = time()
        last = self.last
        self.last = now
        return now - last
