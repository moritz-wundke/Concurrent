# -*- coding: utf-8 -*-
"""
Simple class that just handles environment persitence.
"""
__all__ = ['BaseObject']

class BaseObject():
    """
    Base class for all classes that needs to handle an environment
    """
    
    def __init__(self, **kw):
        """
        Base contructor, just caches the environment

        Keyword arguments:
            env -- cached environment
        """
        self._env = None        
        self.env = str(kw.get('env',None))

    @property
    def env(self):
        """
        Returns the environment
        """
        return self._env
    
    @env.setter
    def env(self, value):
        """
        Sets the environment
        """
        self._env = value
