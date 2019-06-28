import asyncio
from http import HTTPStatus

from aiohttp import ClientSession, ClientResponseError
from aiohttp.hdrs import METH_GET, METH_HEAD

from util.singleton import Singleton


class ContentError(Exception):
    pass


class ResponseError(ContentError):
    def __init__(self, response):
        super().__init__(self._build_error_message(response))
        self.status_code = response.status
        self.status_message = response.reason

    @staticmethod
    def _build_error_message(response):
        return 'Failed to call {method} on {url}: got {statusCode} ({statusMessage})'.format(
            method=response.method,
            url=response.url,
            statusCode=response.status,
            statusMessage=response.reason,
        )


class AsyncContents(metaclass=Singleton):
    _MAX_CHUNK_SIZE = 2 * 1024 * 1024  # 2MB
    _session: ClientSession = None

    async def __aenter__(self):
        if self._session is None:
            self._session = ClientSession()
            return await self._session.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        assert self._session is not None, 'this object was not entered'
        await self._session.__aexit__(exc_type, exc_val, exc_tb)
        self._session = None

    def __await__(self):
        return []

    async def utf8(self, resource, params=None, headers=None):
        response = await self.__raw(
            resource,
            params=params,
            headers=headers,
        )
        return response.decode('utf-8')

    async def __raw(self, resource, params=None, headers=None):
        response = await self.__get_ok(
            resource,
            params=params,
            headers=headers,
        )
        raw_content = response.content.read()
        return await raw_content

    async def json(self, resource, params=None, headers=None):
        response = await self.__get_ok(
            resource,
            params=params,
            headers=headers,
        )
        return await response.json()

    async def __get_ok(self, resource, method=METH_GET, params=None, headers=None):
        response = await self.__get(
            resource,
            method=method,
            params=params,
            headers=headers,
        )
        return self.__check_ok(response)

    async def headers(self, resource):
        response = await self.__get_ok(
            resource,
            method=METH_HEAD,
        )
        return self.__check_ok(response).headers

    async def __get(self, resource, method=METH_GET, params=None, headers=None):
        while True:
            try:
                await self.try_avoiding_connection_errors()
                return await self._session.request(
                    method,
                    resource,
                    params=params,
                    headers=headers,
                    chunked=True,
                    allow_redirects=True,
                    timeout=60,
                )
            except ClientResponseError as e:
                # occurs randomly, just retry
                # https://github.com/aio-libs/aiohttp/issues/2624
                if e.status == 400 and e.message == 'invalid constant string':
                    continue
                raise e

    '''
        try avoiding ClientOsError('cannot write to closing transport') and
        Unclosed connection client_connection: Connection<ConnectionKey(...)>
        by sleeping
        https://github.com/aio-libs/aiohttp/issues/1799
    '''
    @staticmethod
    async def try_avoiding_connection_errors():
        await asyncio.sleep(0.001)

    @staticmethod
    def __check_ok(response):
        if response.status != HTTPStatus.OK:
            raise ResponseError(response)
        return response

    async def chunked(self, resource):
        response = await self.__get_ok(resource)
        return response.content.iter_chunked(self._MAX_CHUNK_SIZE)
