from sys import stderr, stdout, exit


class Log:
    @staticmethod
    def error(msg):
        stderr.write(msg + '\n')
        exit(1)

    @staticmethod
    def info(msg):
        stdout.write(msg)
        stdout.flush()
