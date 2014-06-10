# -*- coding: utf-8 -*-
"""
Basic Concurrent environment
"""
import os, sys
try:
    import threading
except ImportError:
    import dummy_threading as threading
import setuptools
import sqlalchemy
import web

try:
    # Python 2
    from urlparse import urlsplit
except ImportError:
    # Python 3
    from urllib.parse import urlsplit

from concurrent.core.components.component import Component, ComponentManager
from concurrent.core.components.component import implements, ExtensionPoint
from concurrent.core.exceptions.baseerror import BaseError
from concurrent.core.environment.api import IEnvUpgrader, IEnvBackup, IEnvDelete

from concurrent.core.application.api import IApp, APP_RET_CODE_FAILED
from concurrent.core.application.application import ApplicationManager
from concurrent.core.application.application import DEFAULT_APPLICATION

from concurrent.core.logging.log import *

from concurrent.core.util.date import to_datetime, format_time
from concurrent.core.util.utils import get_pkginfo
from concurrent.core.util.texttransforms import _
from concurrent.core.util.texttransforms import printout
from concurrent.core.util.filehandling import create_file, create_dir_gitsafe
from concurrent.core.util.filehandling import  zip_create_from_folder

from concurrent.core.config.config import *

from concurrent.core.db.dbmanager import DatabaseManager

__all__ = ['Environment', 'EnvFolderCheckError', 'EnvWrongVersionError', 'EnvSetup']

class EnvFolderCheckError(BaseError):
    """
    Error raised when the env got bad folders
    """
    title = "[Environment Error]"

class EnvWrongVersionError(BaseError):
    """
    Error raised when the env saved was build with a different version
    """
    title = "[Environment Error]"

class Environment(Component, ComponentManager):
    """
    This is our environment, it represents a real physical structure in disc where a aplications
    life's in.

    The env is a like:

     BasePath/
      - logs/
      - configs/
      - plugins/
      - backups/

    Every folder in our environment needs a dummy file, this file is used in env checks!
    The name of the dummy file is espected to be equal the name of the direct parent folder.
    """

    upgrade_components = ExtensionPoint(IEnvUpgrader)
    backup_components = ExtensionPoint(IEnvBackup)
    delete_components = ExtensionPoint(IEnvDelete)
    
#===============================================================================
# basic environment item
#===============================================================================

    extra_plugins_dir = PathItem('project', 'plugins', '',
        """Path from where we load additional plugins. Apart from
        those we'll load all those located in the path pointed out `plugins`
        env var.""")

    project_name = ConfigItem('project', 'name', 'Concurrent - Project',
        """Name of the project.""")

    project_desc = ConfigItem('project', 'descr',
        'Concurrent - Python apps for everyone!',
        """Short description of the project.""")

    project_app = ExtensionPointItem('project', 'app',
        IApp, DEFAULT_APPLICATION,
        """Application that will run in this environment.""")

#===============================================================================
# logger configurations
#===============================================================================

    log_type = ConfigItem('logging', 'log_type', 'file',
        """type of log we'll use: (`none`, `file`, `stderr`, `syslog`,
         `winlog`)""")

    log_file = ConfigItem('logging', 'log_file', 'env.log',
        """If your log type is `file` this will be the target file""")

    log_level = ConfigItem('logging', 'log_level', 'DEBUG',
        """Python logger Level: (`CRITICAL`, `ERROR`, `WARN`, `INFO`,
         `DEBUG`)""")

    log_format = ConfigItem('logging', 'log_format', None,
        """Custom logging format.

        If nothing is set, the following will be used:

        %(default_format)s

        Format can include regular log tags:
         - http://docs.python.org/library/logging.html#formatter-objects.

        Concurrent addes several new tags':
         - $(app)s          - application that is running in this environment
         - $(path)s         - full environmnet path
         - $(basename)s     - basename of the environmnet path
         - $(project_name)s - current project name that lifes in the env"""
         % {'default_format':get_escaped_default_log_format()})

    def __init__(self, basepath, create=False, args=None):
        """
        Open/create an env.

        @param basepath: The absolute path to our environment
        @param create: If true we'll try to create a new environment in basepath,
            if false we'll load an env (must be created!)
        @param args: List of tuples used to setup the env. The tuples are styled like:
            (section, name, value)
        """
        # handle version and system info
        import concurrent
        from concurrent import __version__ as VERSION
        self.systeminfo = [
            ('concurrent', get_pkginfo(concurrent).get('version', VERSION)),
            ('Python', sys.version),
            ('setuptools', setuptools.__version__),
            ('sqlalchemy', sqlalchemy.__version__),
            ('web.py', web.__version__),
            ]
        
        # Default empty array, do not do this as a default argument!
        # see: http://pylint-messages.wikidot.com/messages:w0102
        if args is None:
            args = []

        self.config = None
        self.log_instance = None
        self.log = None

        ComponentManager.__init__(self)

        self.basepath = basepath

        # Create all directories if needed
        if create:
            self.conditional_create_env_dirs()

        # Setup env config items
        self.setup_config(use_defaults=create)

        # Setup logs
        self.setup_log()

        # Make a separator in the log so we now better when we start
        if create:
            self.log.info("Creating new env...")
        else:
            self.log.info("Launching env...")

        # Now we need to load our components. This needs to be done
        # because we got some components that catches when a new env
        # will be created
        from concurrent.core.components.componentloader import load_components
        plugins_dir = self.extra_plugins_dir
        load_components(self, plugins_dir and (plugins_dir,))

        # initialize db manager
        self.db_manager = DatabaseManager(self)
        self.db_manager.initdb()

        # Initialize APP Manager
        self.app_manager = ApplicationManager(self)

        # Create or check the env :D
        if create:
            self.create(args)
        else:
            # Check if the basepath is set well or not :D
            self.check()

        # inform of creation
        if create:
            for upgrade_component in self.upgrade_components:
                upgrade_component.env_created()

    def launch_main_app(self):
        """
        Method that will launch the registered main app for this environment
        """
        try:
            self.project_app.app_init()
            return self.project_app.app_main()
        except:
            traceback.print_exc()
            return APP_RET_CODE_FAILED

    def get_app_name(self):
        """
        Return name of currently running application
        """
        return self.config.get('project', 'app', DEFAULT_APPLICATION)

    def create(self, args=None):
        """
        Will try to create a new environment. Our basepath has already been set in the
        constructor.

        If args contains ('baseon', 'file'), default values will not be
        loaded; they are expected to be provided by that file or other options.

        @param args: List of tuples used to setup the env. The tuples are styled like:
            (section, name, value)
        """
        from concurrent import __version__ as VERSION

        # Default empty array, do not do this as a default argument!
        # see: http://pylint-messages.wikidot.com/messages:w0102
        if args is None:
            args = []

        # Create base Concurrent files
        create_file(self.get_version_file_path(),
            _('%(version)s\n', version=VERSION))
        create_file(self.get_readme_file_path(),
            'A simple Concurrent environment\n')

        # Create base config file!
        create_file(os.path.join(self.get_configs_dir(),
            self.get_ini_filename()))

        # Setup the default configuration
        skip_defaults = args and ('baseon', 'file') in [(section, option) \
                for (section, option, value) in args]
        self.setup_config(use_defaults=not skip_defaults)
        for section, name, value in args:
            self.config.set(section, name, value)
        self.config.save()
        self.config.conditional_parse()

    def setup_log(self):
        """
        Setup our logger
        """
        self.log_instance = Log(self)
        self.log = self.log_instance.logger

    def setup_config(self, use_defaults=False):
        """
        Will try to load the environment config file using our config reader.
        If we need to use the defaults we'll also regenerate the config file.
        """
        self.config = ConfigHandle(os.path.join(self.get_configs_dir(),
            self.get_ini_filename()))
        if use_defaults:
            for section, default_options in self.config.defaults().items():
                for name, value in default_options.items():
                    if self.config.based_on and \
                        name in self.config.based_on[section]:
                        value = None
                    self.config.set(section, name, value)

    def shutdown(self, tid=None, except_logging=False):
        """Shutdown the environment."""
        # Shutdown db manager
        self.db_manager.dbshutdown()

        # Flush logger
        if tid is None and not except_logging and \
                hasattr(self.log, 'custom_handler'):
            hdlr = self.log.custom_handler
            self.log.removeHandler(hdlr)
            hdlr.flush()
            hdlr.close()
            del self.log.custom_handler
            del self.log


    # -- Component manager overwrites

    def activate_component(self, component):
        """Initialize member vasr of the component.
        Concurrent will initialize the environment (env) the config handle
        (config) and the logger (log)"""
        component.env = self
        component.config = self.config
        component.log = self.log

    def is_component_enabled(self, cls):
        """If a compoent is not enabled but it should be (always enabled
         componentsor such) return true. Otherwise return false and prevent
        enabling."""
        if not isinstance(cls, basestring):
            component_name = (cls.__module__ + '.' + cls.__name__).lower()
        else:
            component_name = cls.lower()

        rules = [(name.lower(), value.lower() in ('enabled', 'on'))
                 for name, value in self.config.items('components')]
        rules.sort(lambda a, b: -cmp(len(a[0]), len(b[0])))

        for pattern, enabled in rules:
            if component_name == pattern or pattern.endswith('*') \
                    and component_name.startswith(pattern[:-1]):
                return enabled

        # By default, all components in the trac package are enabled
        return component_name.startswith('concurrent.')

    def backup_get_default_file_name(self):
        """
        get default backup file name
        """
        time_string = format_time(to_datetime(None), "%Y%m%d_%H%M%S")
        return os.path.join(self.get_backups_dir(), time_string+'.zip')

    def backup(self, source=None, dest=None):
        """
        backup the whole environment to a zip file
        """
        # Create backup dir if not set
        if not os.path.exists(self.get_backups_dir()):
            os.makedirs(self.get_backups_dir())

        # create zip file of all but the backup folder
        if not dest:
            dest = self.backup_get_default_file_name()
        if not source:
            source = self.basepath
        zip_create_from_folder(self.basepath, dest,
            [self.get_backups_dir_name()])

        # Now go through all backup listeners
        for backuper in self.backup_components:
            # TODO: Open the zip file to add stufff to it!
            backuper.env_backup()

    def restored(self):
        """
        Called when this env has been restored
        """
        for restorer in self.backup_components:
            restorer.env_restore()

    def delete(self):
        """
        Delete an environment is like uninstalling it
        """

        printout(_(" Uninstalling Components"))
        for deleter in self.delete_components:
            deleter.env_delete()

        printout(_(" Environment successfully uninstalled"))

    def needs_upgrade(self):
        """Return whether the environment needs to be upgraded."""
        dbmanager = None
        for upgrader in self.upgrade_components:
            if upgrader.env_need_upgrade(dbmanager):
                self.log.warning('Component %s requires environment upgrade',
                    upgrader)
                return True
        return False

    def upgrade(self, backup=False, backup_dest=None):
        """Upgrade database.

        @param backup: whether or not to backup before upgrading
        @param backup_dest: name of the backup file
        @return: whether the upgrade was performed
        """
        dbmanager = None

        upgraders = []
        for upgrader in self.upgrade_components:
            if upgrader.env_need_upgrade(dbmanager):
                upgraders.append(upgrader)
        if not upgraders:
            return False

        if backup:
            self.backup(self.basepath, backup_dest)
        for upgrader in upgraders:
            upgrader.env_do_upgrade(dbmanager)

        # Database schema may have changed, so close all connections
        self.shutdown(except_logging=True)
        return True

    # -- Directory Structure definitions

    def check(self):
        """
        Check if the current basepath is a valid environment. It just checks if all
        directories and needed files are in here.
        """
        # Check environment version
        self.check_version()

        # Check dirs
        self.check_dir(self.get_logs_dir())
        self.check_dir(self.get_configs_dir())
        self.check_dir(self.get_plugins_dir())
        self.check_dir(self.get_backups_dir())
        
        # These are the base folders for any web.py app
        self.check_dir(self.get_sql_dir())
        self.check_dir(self.get_templates_dir())

    def conditional_create_env_dirs(self):
        """
        Create all dirs the environment needs
        """
        # Create the directory structure
        if not os.path.exists(self.basepath):
            os.makedirs(self.basepath)
        create_dir_gitsafe(self.get_logs_dir())
        create_dir_gitsafe(self.get_configs_dir())
        create_dir_gitsafe(self.get_plugins_dir())
        create_dir_gitsafe(self.get_backups_dir())
        
        # we.py required folders
        create_dir_gitsafe(self.get_sql_dir())
        create_dir_gitsafe(self.get_templates_dir())
        
        # Create gitignore in root of env
        create_file(os.path.join(self.basepath,'.gitignore'), '*.log')

    def get_version_from_file(self):
        """
        Return the version saved in the 'VERSION' file of the env
        """
        if not os.path.exists(self.get_version_file_path()):
            raise EnvWrongVersionError(_("Env needs a file called `VERSION` "\
                "to save it's version in the env root."))

        try:
            file_handle = open(self.get_version_file_path(), 'r')
            saved_version = file_handle.read().split()[0]
            return saved_version
        except:
            raise EnvWrongVersionError(_("Version file corrupted!"))

    def check_version(self):
        """
        Checks current installed framework version
        """
        from concurrent import __version__ as VERSION
        saved_version = self.get_version_from_file()
        if saved_version != VERSION:
            raise EnvWrongVersionError(_("Version check failed! Saved " \
                "Version `%(saved_version)s` != Concurrent Version " \
                "`%(concurrent_version)s`" \
                ,saved_version=saved_version,concurrent_version=VERSION))

    @classmethod
    def check_dir(cls, dirname):
        """
        Check if the dir has a file with the same name as it's children
        """
        if not os.path.exists(dirname):
            raise EnvFolderCheckError(_("%(dir)s does not exist!", dir=dirname))

    def get_version_file_path(self):
        """
        Absolute path to the version file
        """
        return os.path.join(self.basepath,'VERSION')

    def get_readme_file_path(self):
        """
        Absolute path to the readme file
        """
        return os.path.join(self.basepath,'README')

    @classmethod
    def get_ini_filename(cls):
        """
        get the filename we use for our main ini
        """
        from concurrent.core.config.config import _INI_FILENAME
        return _INI_FILENAME

    def get_logs_dir(self):
        """
        Absulute path where our logs are
        """
        return os.path.join(self.basepath, self.get_logs_dir_name())

    @classmethod
    def get_logs_dir_name(cls):
        """
        Return the name of the logs folder
        """
        return 'logs'

    def get_configs_dir(self):
        """
        Absulute path where our configs are
        """
        return os.path.join(self.basepath, self.get_configs_dir_name())

    @classmethod
    def get_configs_dir_name(cls):
        """
        Return the name of the configs folder
        """
        return 'configs'

    def get_plugins_dir(self):
        """
        Absulute path where our plugins are
        """
        return os.path.join(self.basepath, self.get_plugins_dir_name())

    @classmethod
    def get_plugins_dir_name(cls):
        """
        Return the name of the plugins folder
        """
        return 'plugins'

    def get_backups_dir(self):
        """
        Absulute path where our backups are
        """
        return os.path.join(self.basepath, self.get_backups_dir_name())

    @classmethod
    def get_backups_dir_name(cls):
        """
        Return the name of the backups folder
        """
        return 'backups'
    
    def get_sql_dir(self):
        """
        Absulute path where our sql schemas are
        """
        return os.path.join(self.basepath, self.get_sql_dir_name())

    @classmethod
    def get_sql_dir_name(cls):
        """
        Return the name of the sql folder
        """
        return 'sql'
    
    def get_templates_dir(self):
        """
        Absulute path where our templates are
        """
        return os.path.join(self.basepath, self.get_templates_dir_name())

    @classmethod
    def get_templates_dir_name(cls):
        """
        Return the name of the templates folder
        """
        return 'templates'

class EnvSetup(Component):
    """
    Component which will act as the setup manager for the environment. Also
    handles main backup/restore procedures if something hapens to the environment
    """
    implements(IEnvUpgrader, IEnvBackup, IEnvDelete)

    # IEnvDelete methods
    def env_delete(self):
        """
        Called when an env get's deleted, env is still valid
        """
        self.log.info("(EnvSetup) Deleting Environment...")


    # IEnvBackup methods
    def env_backup(self):
        """
        Called when we make a backup
        """
        backup_data ={}
        self.log.info("(EnvSetup) Backup Environment...")
        return backup_data

    def env_restore(self):
        """
        Called when we make a restore
        """
        self.log.info("(EnvSetup) Restore Environment...")


    # IEnvUpgrader methods
    def env_created(self):
        """
        Called when a new env has been created
        """
        self.log.info("(EnvSetup) Created Environment...")

    def env_need_upgrade(self, dbManager):
        """
        Called when we start an environment, if this call returns true the env will not able to
        load until we force an upgrade.

        TODO: This needs to be done!
        """
        return False

    def env_do_upgrade(self, dbManager):
        """
        This will perform the actual upgrade process. Be careful on using db transactions
        """
        self.log.info("(EnvSetup) Uprade Environment...")
