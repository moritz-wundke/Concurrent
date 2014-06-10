# -*- coding: utf-8 -*-
"""
Base interface representing an application.
"""
from concurrent.core.components.component import Component, implements, ExtensionPoint
from concurrent.core.application.api import IApp, APP_RET_CODE_SUCCESS
from concurrent.core.exceptions.baseerror import BaseError
from concurrent.core.util.texttransforms import _

DEFAULT_APPLICATION = 'DefaultApplication'

__all__ = ['DefaultApplication', 'ApplicationManager','ApplicationNotImplementedError']

class ApplicationNotImplementedError(BaseError):
    """
    Error used when an app dose not implement a specifc methos
    """
    title="[Config Error]"

class DefaultApplication(Component):
    implements(IApp)
    
    def app_init(self):
        """
        Initialize application just before running it
        """
        self.log.info("Init Default Application...");

    def app_main(self):
        """
        Default Main implementation
        """
        self.log.info("Starting Default Application...");
        self.log.info("Closing Default Application...");
        return APP_RET_CODE_SUCCESS
    
class ApplicationManager(Component):
    """
    The application manager is a component that just handles a list of available applications
    """
    #applications = ExtensionPoint(IApp)

    #def launch(self):
    #    for app in self.applications:
    #        app.app_init()
    #        app.app_main()
