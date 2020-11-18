import json
import os
from os import path


class PersistentJsonResource:
    def __init__(self, file_name):
        self.__file_name = path.expanduser(file_name)
        self.__value = None

    def value(self):
        if self.__value:
            return self.__value
        if path.isfile(self.__file_name):
            with open(self.__file_name, 'r') as resource_file:
                return json.load(resource_file)
        return None

    def store(self, value):
        if value:
            self.__value = value
            os.makedirs(path.dirname(self.__file_name), exist_ok=True)
            with open(self.__file_name, 'w') as resource_file:
                json.dump(value, resource_file)

    def clear(self):
        self.__value = None
        if path.isfile(self.__file_name):
            os.remove(self.__file_name)
