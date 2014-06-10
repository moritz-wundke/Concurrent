# -*- coding: utf-8 -*-
"""
SQL Alchemy engines
"""
from concurrent.core.components.component import Component, implements, ExtensionPoint
from concurrent.core.db.api import IDBEngine
from sqlalchemy import create_engine
from concurrent.core.config.config import ConfigItem, BoolItem
from concurrent.core.util.texttransforms import _
from concurrent.core.exceptions.baseerror import BaseError

__all__ = ['PostGreSQLEngine','EngineCreationFailedError']

class EngineCreationFailedError(BaseError):
    """
    Error raised when we get an engine and we failed
    """
    title="[DB Engine Error]"
    
class PostGreSQLEngine(Component):
    """
    PostGreSQL DB Engine
    """
    implements(IDBEngine)
    
    db_user = ConfigItem('postgresqlengine', 'user', 'postgresql',
        """User name of the postgresql database.""")
    
    db_pass = ConfigItem('postgresqlengine', 'password', '',
        """Password of the postgresql database.""")
    
    db_host = ConfigItem('postgresqlengine', 'host', 'localhost',
        """Host of the postgresql database.""")
    
    db_port = ConfigItem('postgresqlengine', 'port', '5432',
        """Port of the postgresql database.""")
    
    db_name = ConfigItem('postgresqlengine', 'databasename', 'mydb',
        """Name of the postgresql database.""")
    
    db_echo = BoolItem('postgresqlengine', 'echo', True,
        """Use SQL Alchemy debug output.""")
    
    def __init__(self):
        """
        Initialize engine
        """
        self.engine = None
        
    def _get_connection_string(self):
        """
        Private method to build the current connection string
        """
        return _("postgresql://%(user)s:%(password)s@%(host)s:%(port)s/%(dbname)s", 
                              user=self.db_user, password=self.db_pass, 
                              host=self.db_host, port=self.db_port,
                              dbname=self.db_name)
                              
    def get_engine(self):
        """
        Create a PostGreSQL DB Engine
        """
        if not self.engine:  
            self.engine = create_engine( self._get_connection_string(), echo=self.db_echo )
        return self.engine
    
    def initdb(self):
        """
        Called from the dbmanager once it gets initialized
        """
        #if not self.get_engine():
        #    raise EngineCreationFailedError(_("Failed to create db engine for: %(connectionstring)s", connectionstring=self._get_connection_string()))
    
    def dbshutdown(self):
        """
        Called from the dbmanager once it gets shutdown
        """
