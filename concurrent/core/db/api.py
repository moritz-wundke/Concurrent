# -*- coding: utf-8 -*-
"""
API for DB connections
"""
from concurrent.core.components.component import Interface

__all__ = ['IDBEngine']

class IDBEngine(Interface):
    """
    A DB engine represents a component that is used to create a sqlalchemy
    engine.
    """
    def get_engine():
        """
        Return a sqlalchemy engine
        """
    
    def initdb():
        """
        Called from the dbmanager once it gets initialized
        """
    
    def dbshutdown():
        """
        Called from the dbmanager once it gets shutdown
        """
