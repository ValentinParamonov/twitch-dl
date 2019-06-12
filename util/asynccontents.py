from http import HTTPStatus

from aiohttp import ClientSession

from util.log import Log
from util.singleton import Singleton


class AsyncContents(metaclass=Singleton):
    _session: ClientSession = None

    async def __aenter__(self):
        assert self._session is None, 'this object was entered already'
        self._session = ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        assert self._session is not None, 'this object was not entered'
        await self._session.close()
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

    async def __get_ok(self, resource, params=None, headers=None):
        return await self.__check_ok(
            await self.__get(resource, params=params, headers=headers)
        )

    async def headers(self, resource):
        try:
            response = await self._session.head(resource, allow_redirects=True)
            return (await self.__check_ok(response)).headers
        except Exception as e:
            Log.fatal(str(e))
            exit(1)

    async def __get(self, resource, params=None, headers=None):
        try:
            return await self._session.request(
                'GET',
                resource,
                params=params,
                headers=headers,
                chunked=True
            )
        except Exception as e:
            Log.fatal(str(e))
            exit(1)

    async def __check_ok(self, response):
        if response.status != HTTPStatus.OK:
            Log.fatal(
                'Failed to get {url}: got {statusCode} response'.format(
                    url=response.url,
                    statusCode=response.status
                )
            )
            exit(1)
        return response

    async def chunked(self, resource):
        response = await self.__get_ok(resource)
        return await response.content.readchunk()
