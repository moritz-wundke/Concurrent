# -*- coding: utf-8 -*-
"""
Environment related in interfaces
"""
from concurrent.core.components.component import Interface

__all__ = ['IEnvUpgrader','IEnvBackup','IEnvDelete']

class IEnvDelete(Interface):
    """
    Extension point that defines a component which will be able to act when an
    environment gets deleted
    """
    
    def env_delete():
        """
        Called when the current env get's backedup
        """
        
class IEnvBackup(Interface):
    """
    Extension point that defines a component which will be able to act when a backup 
    will be performed.
    """
    
    def env_backup():
        """
        Called when the current env get's backedup
        """
    
    def env_restore():
        """
        Called when we restored the current env from a backup
        """

class IEnvUpgrader(Interface):
    """
    Extension point that defines component which needs to perform any upgrade
    actions
    
    TODO: @Joze: Integrate database manager, needs to be passed to the component
    """

    def env_created():
        """
        Called when a new env has been created
        """

    def env_need_upgrade(dbManager):
        """
        Called when we start an environment, if this call returns true the env will not able to
        load until we force an upgrade.
        """

    def env_do_upgrade(dbManager):
        """
        This will perform the actual upgrade process. Be careful on using db transactions
        """
