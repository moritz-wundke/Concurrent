# -*- coding: utf-8 -*-
"""
Logger class that is able to link to a large number of OS dependent
log's. Apart handles log categories and much more.

TODO:
  * Add categories
  * Add remote log ability
"""
import logging
import logging.handlers
import sys
import os
import traceback

# Simple dict that defines available log levels
_LOG_LEVEL_DICTIONARY = {\
   ('DEBUG','ALL'):logging.DEBUG,\
   ('INFO'):logging.INFO,\
   ('WARN'):logging.WARN,\
   ('ERROR'):logging.WARN,\
   ('CRITICAL'):logging.CRITICAL,\
   }
_LOG_LEVEL_DEFAULT = logging.INFO

# Logtypes
_EXTRA_LOG_TYPE_LIST = ('stderr','file')
_FILE_LOGTYPE_LIST = ('file')
_WIN_LOGTYPE_LIST = ('winlog', 'eventlog', 'nteventlog')
_SYSLOG_LOGTYPE_LIST = ('syslog','unix')
_STREAM_LOGTYPE_LIST = ('stderr')


_DEFAULT_LOG_FORMAT = '[%(project_name)s][%(app)s][%(module)s] %(levelname)s: %(message)s'

def print_trace(msg):
    print(msg)
    for line in traceback.format_stack():
        print line.strip()
    print("\n\n")

def set_extra_log_format(logtype,format):
    if logtype in _EXTRA_LOG_TYPE_LIST:
        format = '%(asctime)s ' + format
    return format

def get_log_level(levelstring):
    for key, value in _LOG_LEVEL_DICTIONARY.items():
        if levelstring in key:
            return value
    return _LOG_LEVEL_DEFAULT

def get_default_log_format():
    return _DEFAULT_LOG_FORMAT

def get_escaped_default_log_format():
    return _DEFAULT_LOG_FORMAT.replace('%', '$')

def logger_factory(logtype='syslog', logfile=None, level='WARNING',
                   logid='concurrent', format=None):
    logger = logging.getLogger(logid)
    logtype = logtype.lower()

    # Make sure we do not use unix logging on windows
    if os.name is 'nt' and logtype in _SYSLOG_LOGTYPE_LIST:
        logtype = _WIN_LOGTYPE_LIST[0]

    if logtype in _FILE_LOGTYPE_LIST:
        hdlr = logging.FileHandler(logfile)
    elif logtype in _WIN_LOGTYPE_LIST:
        hdlr = logging.handlers.NTEventLogHandler(logid, logtype='Application')
    elif logtype in _SYSLOG_LOGTYPE_LIST:
        hdlr = logging.handlers.SysLogHandler('/dev/log')
    elif logtype in _STREAM_LOGTYPE_LIST:
        hdlr = logging.StreamHandler(sys.stderr)
    else:
        hdlr = logging.handlers.BufferingHandler(0)

    datefmt = ''
    if logtype == 'stderr':
        datefmt = '%X'
    level = level.upper()
    logger.setLevel(get_log_level(level))

    formatter = logging.Formatter(format, datefmt)
    hdlr.setFormatter(formatter)

    # Add handler
    logger.addHandler(hdlr)
    
    if (level == 'DEBUG' or level == 'All' or level == 'INFO') and not (logtype in _STREAM_LOGTYPE_LIST):
        logger.addHandler(logging.StreamHandler(sys.stderr))

    # Remember our handler so that we can remove it later
    logger.custom_handler = hdlr

    return logger

class Log():
    """
    Logger class that handles several types of loggin including categories and such
    """

    def __init__(self, env):
        """
        Constructor for our logger. Will initialize all needed structures.
        """

        # Save env
        self.env = env
        self.format = ""

        self.logtype = self.env.log_type
        self.logfile = self.env.log_file

        self._init_format()

        # Check existence of the log file
        if self.logtype == 'file' and not os.path.isabs(self.logfile):
            logfile = os.path.join(env.get_logs_dir(), self.logfile)

        self.logger = logger_factory(self.logtype, logfile, env.log_level, env.basepath,
                                  format=self.format)

    def _init_format(self):
        """
        Initialize the format string for our logger, here we add information of the
        project and it's application we are running
        """
        self.format = self.env.log_format
        if not self.format:
            self.format = _DEFAULT_LOG_FORMAT

        # Look if we need to add some extra stuff to our format
        self.format = set_extra_log_format(self.logtype, self.format)

        if self.format:
            self.format = self.format.replace('$(', '%(') \
                .replace('%(app)s', self.env.get_app_name()) \
                .replace('%(path)s', self.env.basepath) \
                .replace('%(basename)s', os.path.basename(self.env.basepath)) \
                .replace('%(project_name)s', self.env.project_name)



