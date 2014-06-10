# -*- coding: utf-8 -*-
"""
Simple base socket system used in transport protocol based systems
"""
from concurrent.core.transport.api import IClientSocket
from concurrent.core.util.cryptohelper import CryptoHelper
from concurrent.core.util.jsonlib import json

import socket
import struct
import types
import errno
import time
import zmq
import zlib
import base64
try: import cPickle as pickle
except ImportError: import pickle

"""

Out internal protocol:

"""

__all__ = ['IClientSocket', 'send_to', 'receive_from']

VERSION = 1
DEFAULT_PASS = 'kJhvs644vcg21nFd'

HEADER_SIZE = 8
HEADER_FMT = '!Q'
MAX_PACKET_SIZE = 8192
SEND_LIMIT = 128*1024

class NoDataException(Exception):
    """
    Exception raised when no data has been present to be send or to receive
    """

def create_request_dict(method, *args, **kwargs):
    """
    Returns a JSON-RPC-Dictionary for a method

    :param method: Name of the method
    :param args: Positional parameters
    :param kwargs: Named parameters
    """

    if kwargs:
        params = kwargs
        if args:
            params["__args"] = args
    else:
        params = args
    data = {
        "m": unicode(method),
        "v": VERSION,
        "p": params
    }
    return data


def create_request_json(method, *args, **kwargs):
    """
    Returns a JSON-RPC-String for a method

    :param method: Name of the method
    :param args: Positional parameters
    :param kwargs: Named parameters
    """

    return pickle.dumps(create_request_dict(method, *args, **kwargs), protocol=pickle.HIGHEST_PROTOCOL)

END = '\0'

def send_to(sock, method, *args, **kwargs):
    """
    Send data to a given socket
    """
    data = create_request_json(method, *args, **kwargs)
    sock.sendall(base64.b64encode(data)+END)
    # The sleep is just here to ensure that the data is send before we send more
    # data to the same socket. Using ZeroMQ we wont have that issue!
    time.sleep(0.005)

def receive_from(sock, map=None):
    """
    Receive data from a give socket
    """
    total_data=[];data=''
    while True:
        data=sock.recv(8192)
        if END in data:
            total_data.append(data[:data.find(END)])
            break
        total_data.append(data)
        if len(sock)>1:
            #check if end_of_data was split
            last_pair=total_data[-2]+total_data[-1]
            if END in last_pair:
                total_data[-2]=last_pair[:last_pair.find(END)]
                total_data.pop()
                break
    data = b''.join(total_data)
    return pickle.loads(base64.b64decode(data))


def pickle_object(obj, protocol=2):
    """
    Pickle an object to be send over the network
    """
    p = pickle.dumps(obj, protocol)
    return zlib.compress(p)

def unpickle_message(msg):
    """
    Unpickle a message received from the network
    """
    p = zlib.decompress(msg)
    return pickle.loads(p)

def send_to_zmq_zipped(socket, obj, flags=0, protocol=2):
    """pickle an object, and zip the pickle before sending it"""
    return socket.send(pickle_object(obj, protocol), flags=flags)

def send_to_zmq_zipped_multi(socket, identity, obj, flags=0, protocol=2):
    """pickle an object, and zip the pickle before sending it"""
    p = pickle.dumps(obj, protocol)
    z = zlib.compress(p)
    return socket.send_multipart([identity, z], flags=flags)

def receive_from_zmq_zipped(socket, flags=0):
    """inverse of send_zipped_pickle"""
    return unpickle_message(socket.recv(flags))

def send_to_zmq(sock, method, *args, **kwargs):
    """
    Send data to a zmq socket
    """
    send_to_zmq_zipped(sock, create_request_dict(method, *args, **kwargs), flags=0, protocol=2)

def send_to_zmq_multi(sock, identity, msg):
    """
    Send data to a zmq socket
    """
    send_to_zmq_zipped_multi(sock, identity, msg, flags=0, protocol=2)
    
def receive_from_zmq(sock, map=None):
    """
    Receive data from a zmq socket
    """
    return receive_from_zmq_zipped(sock, flags=0)
    
class TCPSocketZMQ(IClientSocket):
    """
    This type of socket is meant to be used on client side when connecting to a ZMQ
    asyn server. The socket features his own identity (unique)
    """
    def __init__(self, identity, host, port):
        # Own context for this socket.
        self.context = zmq.Context()
        
        # Create our ZMQ socket
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.DEALER)
        self.host = host
        self.port = port
        
        # The sockets identity
        self.identity = identity
    
    def send_to(self, method, *args, **kwargs):
        """Send data to a socket"""
        send_to_zmq(self.sock, method, *args, **kwargs)

    def receive_from(self, map=None):
        """Receive data from a socket mapping the received data if
        required"""
        return receive_from(self.sock, map)

    def close(self):
        """Close socket connection"""
        self.socket.close()
        self.context.term()

    def connect(self):
        """Connect to a given host and port"""
        self.sock.connect('tcp://{host}:{port}'.format(host=self.address[0], port=self.address[1]))    

class TCPSocket(IClientSocket):
    """
    Simple TCP stream socket implementation to communicate between a computation
    node server.
    """
    def __init__(self, host, port, node, socket1=None, socket_timeout=None):
        if socket1:
            self.sock = socket1
        else:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.address = (host, port)
            #self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(socket_timeout)
        self.scache = {}
        self.node = node
        
    def send_to(self, method, *args, **kwargs):
        """Send data to a socket"""
        send_to(self.sock, method, *args, **kwargs)

    def receive_from(self, map=None):
        """Receive data from a socket mapping the received data if
        required"""
        return receive_from(self.sock, map)

    def close(self):
        """Close socket connection"""
        self.sock.close()

    def connect(self):
        """Connect to a given host and port"""
        self.sock.connect(self.address)
