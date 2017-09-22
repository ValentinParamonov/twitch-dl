from collections import namedtuple

import requests
from requests import codes as status

from util.log import Log

Content = namedtuple('Content', 'decode')


class Error:
    def __init__(self, value):
        self.headers = value
        self.content = Content(decode=lambda _: value)
        self.json = lambda: value
        self.iter_content = lambda chunk_size: value


class Contents:
    @classmethod
    def utf8(cls, resource, params=None, headers=None, onerror=None):
        return cls.__raw(
            resource,
            params=params,
            headers=headers,
            onerror=onerror
        ).decode('utf-8')

    @classmethod
    def __raw(cls, resource, params=None, headers=None, onerror=None):
        return cls.__get_ok(
            resource,
            params=params,
            headers=headers,
            onerror=onerror
        ).content

    @classmethod
    def json(cls, resource, params=None, headers=None, onerror=None):
        return cls.__get_ok(
            resource,
            params=params,
            headers=headers,
            onerror=onerror
        ).json()

    @classmethod
    def __get_ok(cls, resource, params=None, headers=None, onerror=None):
        return cls.__check_ok(
            cls.__get(resource, params=params, headers=headers),
            onerror=onerror
        )

    @classmethod
    def headers(cls, resource):
        try:
            return cls.__check_ok(requests.head(resource)).headers
        except Exception as e:
            Log.error(str(e))

    @staticmethod
    def __get(resource, params=None, headers=None):
        try:
            return requests.get(
                resource,
                params=params,
                headers=headers,
                stream=True
            )
        except Exception as e:
            Log.error(str(e))

    @staticmethod
    def __check_ok(response, onerror=None):
        if response.status_code != status.ok:
            if onerror is None:
                Log.error(
                    'Failed to get {url}: got {statusCode} response'.format(
                        url=response.url,
                        statusCode=response.status_code
                    )
                )
            else:
                return Error(onerror(response.status_code))
        return response

    @classmethod
    def chunked(cls, resource):
        return cls.__get_ok(resource).iter_content(chunk_size=2048)
