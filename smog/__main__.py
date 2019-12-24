import os
import sys

import trio

from smog.api import SmugMugApi
from smog.index import AlbumIndex, DirectoryIndex


async def main():
    _, index_root, *dirs = sys.argv

    oauth_consumer_key = os.environ['SMUGMUG_API_KEY']
    oauth_consumer_secret = os.environ['SMUGMUG_API_SECRET']
    oauth_token = os.environ['SMUGMUG_OAUTH_ACCESS_TOKEN']
    oauth_token_secret = os.environ['SMUGMUG_OAUTH_TOKEN_SECRET']

    api = SmugMugApi(oauth_consumer_key, oauth_consumer_secret,
                     oauth_token, oauth_token_secret)

    to_sync = []
    dir_by_albumkey = {}
    for dir_path in dirs:
        dir_index = DirectoryIndex(dir_path)
        albumkey = await dir_index.get_albumkey()
        if albumkey is None:
            to_sync.append((dir_index, None))
        elif albumkey in dir_by_albumkey:
            raise Exception('duplicate album key', albumkey)
        else:
            dir_by_albumkey[albumkey] = dir_index

    index_root = trio.Path(index_root)
    authuser_response = await api.get_authuser()
    folder_node_endpoint = authuser_response['Response']['User']['Uris']['Node']
    nodes_response = await api.list_nodes(folder_node_endpoint)
    for node in nodes_response['Response']['Node']:
        if node['Type'] != 'Album':
            continue
        albumkey = node['Uris']['Album'].split('/')[-1]
        album_index = AlbumIndex(index_root / albumkey, api, node['Uris']['Album'])
        if albumkey not in dir_by_albumkey:
            # TODO set an album keyword?
            print('Unregistered SmugMug album', albumkey)
            continue
        dir_index = dir_by_albumkey.pop(albumkey)
        to_sync.append((dir_index, album_index))
    to_sync.extend((d, None) for d in dir_by_albumkey.values())

    async with trio.open_nursery() as nursery:
        for dir_index, album_index in to_sync:
            nursery.start_soon(dir_index.reindex)
            if album_index is not None:
                nursery.start_soon(album_index.reindex)

    async with trio.open_nursery() as nursery:
        for dir_index, album_index in to_sync:
            # list() does not seem to work on async generators
            dir_by_md5 = [x async for x in dir_index.iter_by_md5()]
            if album_index is None:
                album_by_md5 = []
                album_endpoint = None
            else:
                album_by_md5 = [x async for x in album_index.iter_by_md5()]
                album_endpoint = album_index.album_endpoint
            for x in (dir_by_md5, album_by_md5):
                x.append(('x', None)) # sentinel
            dir_idx = album_idx = 0
            while dir_idx < len(dir_by_md5) and album_idx < len(album_by_md5):
                dir_md5, image_filename = dir_by_md5[dir_idx]
                album_md5, image_endpoint = album_by_md5[album_idx]
                if dir_md5 == album_md5:
                    dir_idx += 1
                    album_idx += 1
                elif dir_md5 < album_md5:
                    if album_endpoint is None:
                        album_node_response = await api.create_album_node(folder_node_endpoint, dir_index.dir_path.name)
                        album_endpoint = album_node_response['Response']['Node']['Uris']['Album']
                        albumkey = album_endpoint.split('/')[-1]
                        await dir_index.set_albumkey(albumkey)
                    image_path = dir_index.dir_path / image_filename
                    print('Uploading', image_path)
                    # TODO rate limiting
                    nursery.start_soon(api.upload_image, album_endpoint, image_path)
                    dir_idx += 1
                else:
                    # TODO keywords handled sloppily. should add not overwrite. never unset
                    await api.set_image_keywords(image_endpoint, 'smog-upload; smog-removed')
                    album_idx += 1
            assert dir_idx == len(dir_by_md5) and album_idx == len(album_by_md5)


if __name__ == '__main__':
    trio.run(main)
