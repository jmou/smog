# Reset all album and image keywords to smog.upload.

import itertools
import logging
import os
import sys
from async_generator import asynccontextmanager

import trio

from smog.api import SmugMugApi


# TODO refactor pagination logic
async def list_nodes(api, next_page):
    while next_page:
        nodes_response = await api.list_nodes(next_page)
        for node in nodes_response['Response'].get('Node', []):
            yield node
        next_page = nodes_response['Response']['Pages'].get('NextPage')


async def reset_image_keywords(limit, api, image_endpoint):
    async with limit:
        print(f'Resetting keywords {image_endpoint}')
        await api.set_keywords(image_endpoint, 'smog.upload')


async def main():
    _, root_folder = sys.argv

    oauth_consumer_key = os.environ['SMUGMUG_API_KEY']
    oauth_consumer_secret = os.environ['SMUGMUG_API_SECRET']
    oauth_token = os.environ['SMUGMUG_OAUTH_ACCESS_TOKEN']
    oauth_token_secret = os.environ['SMUGMUG_OAUTH_TOKEN_SECRET']

    api = SmugMugApi(oauth_consumer_key, oauth_consumer_secret,
                     oauth_token, oauth_token_secret)

    authuser_response = await api.get_authuser()
    folder_node_endpoint = authuser_response['Response']['User']['Uris']['Node']
    while root_folder:
        if not root_folder.endswith('/'):
            root_folder += '/'
        next_part, root_folder = root_folder.split('/', 1)
        async for node in list_nodes(api, folder_node_endpoint):
            if node['Name'] == next_part:
                folder_node_endpoint = node['Uri']
                break
        else:
            raise Exception('No folder', next_part)

    async for node in list_nodes(api, folder_node_endpoint):
        if node['Type'] != 'Album':
            continue
        albumkey = node['Uris']['Album'].split('/')[-1]
        album_endpoint = '/api/v2/album/' + albumkey
        print(f'Resetting keywords {album_endpoint}')
        await api.set_keywords(album_endpoint, 'smog.upload')
        next_page = album_endpoint
        while next_page:
            album_response = await api.list_images(next_page)
            async with trio.open_nursery() as nursery:
                limit = trio.CapacityLimiter(8)
                for image in album_response['Response'].get('AlbumImage', []):
                    nursery.start_soon(reset_image_keywords, limit, api, image['Uri'])
            next_page = album_response['Response']['Pages'].get('NextPage')


if __name__ == '__main__':
    trio.run(main)
