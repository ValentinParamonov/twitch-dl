import asyncio

from util.asynccontents import AsyncContents


async def main():
    async with AsyncContents() as cl:
        print(await cl.headers('https://jsonplaceholder.typicode.com/todos/1'))
        print(await cl.json('https://jsonplaceholder.typicode.com/todos/1'))
        print(await cl.utf8('https://jsonplaceholder.typicode.com/todos/1'))
        print(await cl.chunked('https://jsonplaceholder.typicode.com/todos/1'))


asyncio.run(main())
