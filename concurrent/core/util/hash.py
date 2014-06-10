# -*- coding: utf-8 -*-
"""
Simple hashing module, used to handle different type of hashes for
clients, clusters, discover servers, etc...
"""
# Include md5 and sha1 functions for both python 2 and 3
try:
    import hashlib
    sha_new = hashlib.sha1
    md5_new = hashlib.md5
except ImportError:
    import sha
    import md5
    sha_new = sha.new
    md5_new = md5.new

# Default secret if none has been provided. Make this configurable?
DEFAULT_SECRET = "2(5BV7|R-4yw<g->"

def hash_data(data, secret=DEFAULT_SECRET, hash_method=sha_new):
    """
    Hash a given data string using a secret and a hash method.
    """
    return hash_method(data+secret).hexdigest()


def hash_sha(data, secret=DEFAULT_SECRET):
    """
    Hash a a given data string using SHA1 and a secret
    """
    hash_data(data, secret, sha_new)

def hash_md5(data):
    """
    Hash a a given data string using MG5
    """
    hash_data(data, '', md5_new)
