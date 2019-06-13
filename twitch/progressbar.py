import os
from sys import stdout


class ProgressBar:
    def __init__(self, file_name, total_segments):
        self.fileName = file_name
        self.total = total_segments
        self.current = 0
        self.update_by(0)

    def update_by(self, count):
        self.current += count
        percent_completed = self.current / self.total * 100
        self.__print_bar(percent_completed)

    def __print_bar(self, percent_completed):
        stdout.write('\r' + ' ' * self.__get_console_width())
        stdout.write('\r{file} [{percents:3.0f}%]{terminator}'.format(
            file=self.fileName,
            percents=percent_completed,
            terminator='\n' if self.current == self.total else ''))

    @staticmethod
    def __get_console_width():
        _, width = os.popen('stty size', 'r').read().split()
        return int(width)
