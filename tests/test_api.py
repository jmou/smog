import unittest.mock

import asks
import pytest
import trio.testing

from smog.api import SmugMugApi


# unittest.mock.AsyncMock not available until Python 3.8
class MockRequest(object):
    def __init__(self):
        self.reset()

    def reset(self, code=200):
        self.args = None
        self.kwargs = None
        self.status_code = code

    async def __call__(self, *args, **kwargs):
        assert self.args is None
        assert self.kwargs is None
        self.args = args
        self.kwargs = kwargs
        return self

    def assert_called_once_with(self, *args, **kwargs):
        assert self.args == args
        assert self.kwargs == kwargs

    def json(self):
        return {}


@trio.testing.trio_test
async def test_api(monkeypatch):
    request = MockRequest()
    monkeypatch.setattr(asks, 'request', request)
    api = SmugMugApi('consumer key', 'consumer secret', 'token', 'token secret',
                     nonce='172302863994516684631577132899', timestamp='1577132899')

    assert await api.get_authuser() == {}
    AUTH_PREFIX = 'OAuth oauth_nonce="172302863994516684631577132899", oauth_timestamp="1577132899", oauth_version="1.0", oauth_signature_method="HMAC-SHA1", oauth_consumer_key="consumer%20key", oauth_token="token", oauth_signature='
    request.assert_called_once_with('GET', 'https://api.smugmug.com/api/v2!authuser?_verbosity=1',
                                    headers={'Accept': 'application/json', 'Accept-Encoding': 'gzip',
                                             'Authorization': AUTH_PREFIX + '"g3SvkYxyiqYSAsBi%2BsaC2Q%2F2H%2Bk%3D"'},
                                    data=None)

    request.reset()
    assert await api.create_album_node('/api/v2/node/node0', 'name') == {}
    request.assert_called_once_with('POST', 'https://api.smugmug.com/api/v2/node/node0!children?_verbosity=1',
                                    headers={'Accept': 'application/json', 'Accept-Encoding': 'gzip',
                                             'Authorization': AUTH_PREFIX + '"Rp1IreISDFYqb8aPYz5umbe4Y9M%3D"',
                                             'Content-Type': 'application/x-www-form-urlencoded'},
                                    data={'Type': 'Album', 'Name': 'name', 'Privacy': 'Private', 'Keywords': 'smog.upload'})

    request.reset()
    async def read_bytes(self):
        return b'bytes'
    monkeypatch.setattr(trio.Path, 'read_bytes', read_bytes)
    assert await api.upload_image('/api/v2/album/album0', 'my/image.jpg') == {}
    request.assert_called_once_with('POST', 'https://upload.smugmug.com/',
                                    headers={'Accept': 'application/json', 'Accept-Encoding': 'gzip',
                                             'Authorization': AUTH_PREFIX + '"VpRi1%2Bg0W7ew2UlHYN0yLdPay30%3D"',
                                             'Content-Length': '5',
                                             'Content-MD5': '4b3a6218bb3e3a7303e8a171a60fcf92',
                                             'Content-Type': 'image/jpeg',
                                             'X-Smug-AlbumUri': '/api/v2/album/album0',
                                             'X-Smug-FileName': 'image.jpg',
                                             'X-Smug-Keywords': 'smog.upload',
                                             'X-Smug-ResponseType': 'JSON',
                                             'X-Smug-Version': 'v2'},
                                    data=b'bytes')
