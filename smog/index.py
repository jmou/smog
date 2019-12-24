import hashlib
import json

import trio


class DirectoryIndex(object):
    def __init__(self, dir_path):
        self.dir_path = trio.Path(dir_path)
        self.index_path = self.dir_path / '.smog' / 'index'
        self.albumkey_path = self.dir_path / '.smog' / 'albumkey'
        self.cache = None

    async def get_albumkey(self):
        if not await self.albumkey_path.exists():
            return None
        return await self.albumkey_path.read_text()

    async def set_albumkey(self, albumkey):
        await self.albumkey_path.parent.mkdir(exist_ok=True)
        await self.albumkey_path.write_text(albumkey)

    async def _load_cache(self):
        self.cache = {}
        if await self.index_path.exists():
            async with await self.index_path.open() as index_file:
                async for line in index_file:
                    md5, size, mtime, filename = line.rstrip('\n').split(' ', 3)
                    self.cache[(size, mtime, filename)] = md5

    async def reindex(self):
        if self.cache is None:
            await self._load_cache()
        entries = list(await self.dir_path.iterdir())
        entries.sort()
        await self.index_path.parent.mkdir(exist_ok=True)
        async with await self.index_path.open('w') as index_file:
            for entry in entries:
                # TODO .mp4 and .mov?
                if not await entry.is_file() or entry.suffix.lower() not in ('.jpg', '.png'):
                    continue
                stat = await entry.stat()
                size = stat.st_size
                mtime = stat.st_mtime_ns
                md5 = self.cache.get((size, mtime, entry.name))
                if md5 is None:
                    md5 = hashlib.md5(await entry.read_bytes()).hexdigest()
                await index_file.write(f'{md5} {size} {mtime} {entry.name}\n')
        await self._load_cache()

    async def iter_by_md5(self):
        if self.cache is None:
            await self._load_cache()
        by_name = [(len(filename), filename, md5)
                   for (_, _, filename), md5 in self.cache.items()]
        by_name.sort()
        seen_md5 = set()
        by_md5 = []
        for _, filename, md5 in by_name:
            # TODO do something more helpful with duplicates
            if md5 in seen_md5:
                print('Skipping duplicate', self.dir_path / filename)
                continue
            seen_md5.add(md5)
            by_md5.append((md5, filename))
        # yield from still not allowed in async function
        for x in sorted(by_md5):
            yield x


class AlbumIndex(object):
    def __init__(self, index_path, api, album_endpoint):
        self.index_path = trio.Path(index_path)
        self.api = api
        self.album_endpoint = album_endpoint
        self.by_md5 = None

    def _load_json(self, json_data):
        self.by_md5 = [(image['ArchivedMD5'], image['Uri'])
                       for image in json_data['AlbumImage']]
        self.by_md5.sort()

    async def reindex(self):
        album_images = []
        next_page = self.album_endpoint
        while next_page:
            album_response = await self.api.list_images(next_page)
            album_images += album_response['Response'].get('AlbumImage', [])
            next_page = album_response['Response']['Pages'].get('NextPage')
        json_data = {'AlbumImage': album_images}
        await self.index_path.write_text(json.dumps(json_data))
        self._load_json(json_data)

    async def iter_by_md5(self):
        if self.by_md5 is None:
            if await self.index_path.exists():
                self._load_json(json.loads(await self.index_path.read_text()))
            else:
                self.by_md5 = []
        for x in self.by_md5:
            yield x
