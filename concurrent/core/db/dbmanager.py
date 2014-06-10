# -*- coding: utf-8 -*-
"""
DataBase Manager
"""
from concurrent.core.components.component import Component, implements, ExtensionPoint
from concurrent.core.db.api import IDBEngine
from concurrent.core.config.config import ExtensionPointListItem

__all__ = ['DatabaseManager']

class DatabaseManager(Component):
    """
    Class that handles connection and high-level database access
    """
    engines = ExtensionPoint(IDBEngine)
    
    db_engines = ExtensionPointListItem('database', 'engine', IDBEngine, 'PostGreSQLEngine',
        """Available DB engines that we can use""")
    
    def initdb(self):
        """
        Initialize all engines we need
        """
        for engine in self.db_engines:
            engine.initdb()
    
    def dbshutdown(self):
        """
        Inform engines that we should shutdown
        """
        for engine in self.engines:
            engine.dbshutdown()
