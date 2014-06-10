# -*- coding: utf-8 -*-
"""
API for transport related modules
"""
from concurrent.core.components.component import Interface
from concurrent.core.util.hash import hash_sha, hash_md5

__all__ = ['IClientSocket', 'IThreadedSocketServer']

# This is not the SDK version! It's the internal transport version
# different SDK can communicate but not different transport protocols!
version = "0.0.1"

# The min SDK version that the current transport protocol supports
version_sdk_min = "0.0.1"

# Responses used when communcating on the control channel
RESPONSE_OK = "C:OK"

class IClientSocket(object):
    """
    Basic socket interface
    """

    def send(self, data):
        """Send data to a socket"""
        raise NotImplementedError("send(self, data) method missing");

    def receive(self, map=None):
        """Receive data from a socket mapping the received data if 
        required"""
        raise NotImplementedError("send(self, map) method missing");

    def close(self):
        """Close socket connection"""
        raise NotImplementedError("close(self) method missing");

    def connect(self, host, port):
        """Connect to a given host and port"""
        raise NotImplementedError("connect(self, host, port) method missing");
