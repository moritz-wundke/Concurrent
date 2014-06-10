# -*- coding: utf-8 -*-
"""
Base interface representing an application.
"""
from concurrent.core.components.component import Interface

__all__ = ['IApp', 'NodeType', 'NodeState']

# Some constants used here
APP_RET_CODE_SUCCESS = 0
APP_RET_CODE_NONE = None
APP_RET_CODE_FAILED = 1
SUCCESS_RET_CODES = [APP_RET_CODE_SUCCESS, APP_RET_CODE_NONE]

class NodeType(object):
    """
    Node types that life in the framework
    """
    invalid = -1
    master = 0
    slave = 1
    client = 2

class NodeState(object):
    """
    Node state within the framework
    """
    invalid = -1
    pending = 0         # Node is waiting for the compute channel registration to complete
    active = 1
    inactive = 2        # Node has been marked as inactive
    inactive_forced = 3

class IApp(Interface):
    """
    Extension point that defines a component that will be handled as an application.
    Applications are components that run in an environment
    """
    
    def app_init():
        """
        Initialize application just before running it
        """
    
    def app_main():
        """
        Main entry point for the application. The app should return a return code or None
        """

class IPickler(Interface):
    """
    Extension point that defines a component used to provide pickling functionality
    """
    
    def pickle_f(fname, obj):
        """
        picke an object into a file
        """
    
    def unpickle_f(fname):
        """
        Unpicke an object from a file
        """
    
    def pickle_s(obj):
        """
        pickle an object and return the pickled string
        """
    def pickle_encode_s(obj):
        """
        Encode a pickled object
        """
        
    def unpickle_s(pickle_string):
        """
        inpickle a string and return an object
        """
    
    def unpickle_decode_s(pickle_string):
        """
        Unpickle a base64 string and return an object
        """