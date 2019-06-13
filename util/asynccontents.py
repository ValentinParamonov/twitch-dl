from http import HTTPStatus

from aiohttp import ClientSession

from util.singleton import Singleton


class AsyncContents(metaclass=Singleton):
    _MAX_CHUNK_SIZE = 65536  # 64KB
    _session: ClientSession = None

    async def __aenter__(self):
        if self._session is None:
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
            raise e

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
            raise e

    @staticmethod
    async def __check_ok(response):
        if response.status != HTTPStatus.OK:
            error_message = 'Failed to get {url}: got {statusCode} response'.format(
                url=response.url,
                statusCode=response.status
            )
            raise Exception(error_message)
        return response

    async def chunked(self, resource):
        response = await self.__get_ok(resource)
        return response.content.iter_chunked(self._MAX_CHUNK_SIZE)
