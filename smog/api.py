import hashlib
import mimetypes
import os

import asks
import oauthlib.oauth1
import trio


class SmugMugApi(object):
    BASE_URI = 'https://api.smugmug.com'

    def __init__(self, oauth_consumer_key, oauth_consumer_secret,
                 oauth_token, oauth_token_secret, **oauth_kwargs):
        self.client = oauthlib.oauth1.Client(
            oauth_consumer_key, client_secret=oauth_consumer_secret,
            resource_owner_key=oauth_token, resource_owner_secret=oauth_token_secret,
            **oauth_kwargs)
        self.request_semaphore = trio.Semaphore(8)

    async def _request_json(self, method, uri, headers=None, body=None):
        if uri.startswith('/'):
            symbol = '&' if '?' in uri else '?'
            uri = self.BASE_URI + uri + symbol + '_verbosity=1'
        if headers is None:
            headers = {}
        headers = {'Accept': 'application/json', 'Accept-Encoding': 'gzip', **headers}

        if headers.get('Content-Type') == 'application/x-www-form-urlencoded':
            uri, headers, body = self.client.sign(uri, http_method=method,
                                                  headers=headers, body=body)
        else:
            # oauthlib barfs on non-UTF8 file upload bodies. These bodies are
            # unsigned in OAuth anyway.
            uri, headers, _ = self.client.sign(uri, http_method=method, headers=headers)

        async with self.request_semaphore:
            response = await asks.request(method, uri, headers=headers, data=body)
        if 200 <= response.status_code < 300:
            pass # TODO error handling
        return response.json()

    async def get_authuser(self):
        return await self._request_json('GET', '/api/v2!authuser')

    async def list_nodes(self, folder_node_endpoint):
        return await self._request_json('GET', folder_node_endpoint + '!children')

    async def create_album_node(self, folder_node_endpoint, album_name):
        return await self._request_json('POST', folder_node_endpoint + '!children',
                                        headers={'Content-Type': 'application/x-www-form-urlencoded'},
                                        body={'Type': 'Album', 'Name': album_name, 'Privacy': 'Private'})

    async def list_images(self, album_endpoint):
        return await self._request_json('GET', album_endpoint + '!images')

    async def set_image_keywords(self, image_endpoint, keywords):
        return await self._request_json('PATCH', image_endpoint,
                                        headers={'Content-Type': 'application/x-www-form-urlencoded'},
                                        body={'Keywords': keywords})

    async def upload_image(self, album_endpoint, image_path):
        image_path = trio.Path(image_path)
        content_type, _ = mimetypes.guess_type(image_path.name)
        body = await image_path.read_bytes()
        headers = {
            'Content-Length': str(len(body)),
            'Content-Type': content_type,
            'Content-MD5': hashlib.md5(body).hexdigest(),
            'X-Smug-AlbumUri': album_endpoint,
            'X-Smug-FileName': image_path.name,
            'X-Smug-Keywords': 'smog-upload',
            'X-Smug-ResponseType': 'JSON',
            'X-Smug-Version': 'v2',
        }
        return await self._request_json('POST', 'https://upload.smugmug.com/',
                                        headers=headers, body=body)


async def main():
    oauth_consumer_key = os.environ['SMUGMUG_API_KEY']
    oauth_consumer_secret = os.environ['SMUGMUG_API_SECRET']
    oauth_token = os.environ['SMUGMUG_OAUTH_ACCESS_TOKEN']
    oauth_token_secret = os.environ['SMUGMUG_OAUTH_TOKEN_SECRET']

    api = SmugMugApi(oauth_consumer_key, oauth_consumer_secret,
                     oauth_token, oauth_token_secret)

    authuser_response = await api.get_authuser()
    folder_node_endpoint = authuser_response['Response']['User']['Uris']['Node']
    album_node_response = await api.create_album_node(folder_node_endpoint, 'test')
    album_endpoint = album_node_response['Response']['Node']['Uris']['Album']
    await api.upload_image(album_endpoint, 'image.png')


if __name__ == '__main__':
    trio.run(main)
