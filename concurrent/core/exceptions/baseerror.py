"""
Base class for more old-school errors, very simple but sometimes hopefull
if you do not whish it too automatic
"""
# Define what do we got in here
__all__ = ['BaseError', 'ErrorCodeMap']

import traceback

class ErrorCodeMap(object):
    """Map of all error codes the framework uses"""
    PickleException = -10001
    UnpickleException = -10002

class BaseError(Exception):
    """Exception base class for errors."""

    title = '[Error]'
    
    def __init__(self, message, title=None, show_traceback=False):
        """
        Simple exception class that just has a title and a message.
        Apart from showing the current traceback or not.
        """
        Exception.__init__(self, message)
        self._message = message
        if title:
            self.title = title
        self.show_traceback = show_traceback

    message = property(lambda self: self._message, 
                       lambda self, v: setattr(self, '_message', v))

    def __unicode__(self):
        return unicode(self.message)
    
    def __str__(self):
        trace=""
        if self.show_traceback:
            trace = "\n%s" % (traceback.format_exc())
        return "%s: %s%s" % (self.title, self._message, trace )
