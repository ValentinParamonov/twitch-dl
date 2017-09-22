from sys import stderr, stdout, exit


class Log:
    @staticmethod
    def error(msg):
        stderr.write(msg + '\n')
        stderr.flush()
        exit(1)

    @staticmethod
    def info(msg):
        stdout.write(msg + '\n')
        stdout.flush()
