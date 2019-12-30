# smog - a type of cloud

Syncs images from your local directories up to SmugMug.

## Installation

Create and activate a Python virtualenv using the method of your choice.

```
$ pip install pip-tools
$ pip-sync requirements.txt
```

## Usage

Activate your virtualenv.

```
$ export SMUGMUG_API_KEY=<fillme>
$ export SMUGMUG_API_SECRET=<fillme>
$ export SMUGMUG_OAUTH_ACCESS_TOKEN=<fillme>
$ export SMUGMUG_OAUTH_TOKEN_SECRET=<fillme>
$ export ALBUM_PASSWORD=<fillme>
$ python3 -m smog <smugmug folder> <local index directory> <directories to upload>
```

Every album will be set to unlisted with the specified album password. This is
an easy way to keep your photos private until you're ready. Unlike being in a
private album, images in these unlisted albums are visible in other albums where
they are collected.

\<smugmug folder> should be a folder in SmugMug to upload into.

\<local index directory> can be any local directory you create. smog will create
index files in this directory.

\<directories to upload>. smog will store data in `.smog` directories in each
uploaded directory.
