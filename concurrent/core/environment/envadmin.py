# -*- coding: utf-8 -*-
"""
Basic command line application
"""
import os
import pkg_resources
import sys
import traceback

from concurrent import __version__ as VERSION
import concurrent.tools.console
from concurrent.core.util.texttransforms import to_unicode, raw_input, _, printerr, printout
from concurrent.core.exceptions.baseerror import BaseError
from concurrent.core.environment.environment import Environment
from concurrent.core.util.filehandling import zip_is_valid,purge_dir
from concurrent.core.config.config import _INI_FILENAME, get_true_values
from concurrent.core.application.api import SUCCESS_RET_CODES

# Our version numbers are handeled by setuptools
try:
    CONCURRENT_VERSION = pkg_resources.get_distribution('Concurrent').version
except:
    CONCURRENT_VERSION = 0

class RecoverBackupFileError(BaseError):
    """
    Simple error used when trying to recover an env from a backup file
    """
    title="[Recover Backup Error]"

class EnvAdmin(concurrent.tools.console.CMD):
    """
    Bash application that helps us with our env's.
    """

    # Definitions we need (see cmd.Cmd for more info)
    doc_header = 'Concurrent Admin Console %(version)s\n' \
                 'Available Commands:\n' \
                 % {'version': CONCURRENT_VERSION}
    prompt = "Con> "

    def print_interactive_header(self):
        printout(_("""[Welcome to Concurrent Environment Admin] %(version)s
Copyright (c) 2014 Moritz Wundke

Type:  '?' or 'help' for help on commands.
        """, version=CONCURRENT_VERSION))

    def print_version(self):
        """
        Print version of app
        """
        printout(os.path.basename(sys.argv[0]), CONCURRENT_VERSION)

#===============================================================================
# Environmnet Helpers
#===============================================================================

    def set_env(self, name, env=None):
        """
        Set a new env to be used
        """
        concurrent.tools.console.CMD.set_env(self, name, env)

        if env is not None:
            self.__env = env

        # Set the new prompt :P
        self.prompt = "Con-[%s]> " % (self.envname)

    def open_env(self):
        """
        Opens the currently selected environment
        """
        try:
            if not self.__env:
                self.__env = Environment(self.envname)
        except Exception as e:
            printerr(_("Ups... I could not open the environment!"), e )
            traceback.print_exc()
            sys.exit(1)

    def ceck_env(self, print_error=False):
        """
        Will return true if the environment can be opened and false otherwise
        """
        try:
            self.__env = Environment(self.envname)
        except Exception as e:
            if print_error:
                printerr(_("Ups... I could not open the environment!"), e )
                traceback.print_exc()
            return False
        return True

#===============================================================================
# Commands - Help
#===============================================================================
    def print_help_header(self):
        printout(_("Concurrent - Environment Admin"))

    def print_usage_help(self):
        printout(_("Usage: con-admin </path/to/project> "
                   "[command [subcommand] [option ...]]\n")
            )
        printout(_("Invoking con-admin without command starts "
                   "interactive mode."))

    def all_docs(cls):
        """
        Add specifc help content
        """
        return (
                concurrent.tools.console.CMD.all_docs() +
                cls._help_plugin +
                cls._help_createenv +
                cls._help_launchenv +
                cls._help_backup +
                cls._help_recover +
                cls._help_update +
                cls._help_delete +
                cls._help_setdefault
                )

    all_docs = classmethod(all_docs)

#===============================================================================
# Commands - Quit
#===============================================================================

    def do_quit(self, line):
        """
        Exit app
        """
        # cleanup the env if there is any open
        try:
            self.__env.shutdown()
        except:
            # Nothing to cleanup
            pass

        # Now finish exit
        concurrent.tools.console.CMD.do_quit(self, line)

#===============================================================================
# Commands - Plugin stuff (admin what we got enabled and what not :P)
#===============================================================================

    _help_plugin = [
                    ('plugin list','Show a list of available plugins'),
                    ('plugin setapp <name>','Will set a plugin to be the standart app to run in this environment ')
                    ]

    def complete_plugin(self, text, line, begidx, endidx):
        comp = ['list', 'setapp']
        return self.word_complete(text, comp)

    # TODO: Make plugins configurable here!
    def do_plugin(self, line):
        args = self.unicod_safe_split(line)
        if args[0] == 'list':
            printout(_("TODO: register plugins"))
        elif args[0] == 'setapp' and len(args)==2:
            printout(_("TODO: set app to life in env"))
        else:
            self.do_help ('plugin')

#===============================================================================
# Commands - Environment launching
# TODO: Finish components/config in environment
# TODO: Add daemonize process into launch option!
#===============================================================================
    _help_launchenv = [('launchenv','Launch app in env (default app)')]

    def do_launchenv(self, line):
        """
        launch the current app or a different one in the env.
        Different apps are usful to testing reasons!
        """
        def launchenv_error(msg):
            printerr(_("Launchenv for '%(env)s' failed:", env=self.envname),
                     "\n", msg)

        # Open env
        if not self.ceck_env(True):
            launchenv_error("Environment not created or corrupted!")
            return 2

        # launch application
        retcode = self.__env.launch_main_app()
        if retcode in SUCCESS_RET_CODES:
            self.__env.log.info("Executed successfully!")
        else:
            self.__env.log.error("Execution failed!")
        
        import threading
        self.__env.log.error("Active threads:")
        for thread in threading.enumerate():
            self.__env.log.error(" - %s" % str(thread))
            
        # Close environment!
        self.__env.shutdown()
        
        # Make sure we kill us :D
        sys.exit(retcode)

#===============================================================================
# Commands - Environment Creation
#===============================================================================

    _help_createenv = [
                       ('createenv','Create and initialize a new environment interactively'),
                       ('createenv </path/to/project> <project_name> <targetapp>','Create and initialize a new environment')
                      ]

    def get_createenv_data(self):
        returnvals = []

        # Basic instructions
        self.print_line()
        printout(_("""Starting Interactive environment creation at <%(envname)s>

This is the interactive guide on environment creation.
Just follow the instructions.""",
                   envname=self.envname))
        self.print_line()

        # Env path
        printout(_(""" Now enter the absolute path where your environment should be created."""))
        path = self.envname
        returnvals.append(raw_input(_("</path/to/project> [%(default)s]> ",
                                      default=path)).strip() or path)
        self.print_line()

        # Environment app
        printout(_(""" Enter the name of the project you are about to create"""))
        path = "My Project"
        returnvals.append(raw_input(_("project_name [%(default)s]> ",
                                      default=path)).strip() or path)
        self.print_line()
        return returnvals

    def do_createenv(self, line):
        """
        Create environment by passed arguments or interactively
        """
        def createenv_error(msg):
            printerr(_("Createenv for '%(env)s' failed:", env=self.envname),
                     "\n", msg)

        if self.ceck_env():
            createenv_error("Environment already created in specified path!")
            return 2

        if os.path.exists(self.envname) and os.listdir(self.envname):
            createenv_error("Target folder not empty!")
            return 2

        project_name = None
        # get arguments
        args = self.unicod_safe_split(line)
        if len(args) == 1 and not args[0]:
            returnvals = self.get_createenv_data()
            path, project_name = returnvals
        elif len(args) != 2:
            createenv_error('Wrong number of arguments: %d' % len(args))
            return 2
        else:
            path, project_name = args[:2]

        try:
            # Uppdate promt and internal stuff
            self.set_env(path)

            # Start env creation
            printout(_("Creating and Initializing Environment"))
            options = [
                ('env', 'path', self.envname),
                ('project', 'name', project_name),
            ]

            # OVER-WRITE THESE OPTIONS from a file

            try:
                self.__env = Environment(self.envname, create=True, args=options)
            except Exception as e:
                # Bad thing happened!
                createenv_error('Failed to create environment. Created files will be deleted')
                printerr(e)
                traceback.print_exc()
                purge_dir( path )
                sys.exit(1)

        except Exception as e:
            createenv_error(to_unicode(e))
            traceback.print_exc()
            return 2

        # Close environment!
        self.__env.shutdown()

        self.print_line()
        printout(_("""Project environment for '%(project_name)s' created.

You may now configure the environment by editing the file:

  %(config_path)s

Have a nice day!
""", project_name=project_name, project_path=self.envname,
           project_dir=os.path.basename(self.envname),
           config_path=os.path.join(self.__env.get_configs_dir(), _INI_FILENAME)))

#===============================================================================
# Update environment
#===============================================================================

    _help_update = [
                    ('update', 'Update environment interactively'),
                    ('update </path/to/project>', 'Update environment')
                   ]
    def do_update(self, line):
        pass

#===============================================================================
# Set default values to env
#===============================================================================

    _help_setdefault = [
                    ('setdefault', 'Set default values to env')
                   ]
    def do_setdefault(self, line):
        pass

#===============================================================================
# Delete environment
#===============================================================================

    _help_delete = [
                    ('delete', 'Delete environment interactively'),
                    ('delete </path/to/project>', 'Delete environment')
                   ]

    def get_delete_data(self):
        returnvals = []
        # Basic instructions
        self.print_line()
        printout(_("""Starting Interactive environment deletion at <%(envname)s>""",
                   envname=self.envname))
        self.print_line()

        # Env path
        printout(_(""" Now enter the absolute path to the environment that will be deleted."""))
        path = self.envname
        returnvals.append(raw_input(_("</path/to/project> [%(default)s]> ",
                                      default=path)).strip() or path)
        self.print_line()
        return returnvals

    def do_delete(self, line):
        def delete_error(msg):
            printerr(_("Delete for '%(env)s' failed:", env=self.envname),
                     "\n", msg)

        # get arguments
        env_dir = None
        args = self.unicod_safe_split(line)

        # Interactive or not
        interactive_delete = False

        if len(args) == 1 and not args[0]:
            returnvals = self.get_delete_data()
            env_dir = returnvals[0]
            interactive_delete = True
        elif len(args) != 1:
            delete_error('Wrong number of arguments: %d' % len(args))
            return 2
        else:
            env_dir = args[0]

        # Set the right env dir
        self.envname = env_dir

        if self.__env and self.__env.basepath == self.envname:
            delete_error("Can not delete currently open environment! Close and open the admin!")
            return 2

        # Open env
        if not self.ceck_env():
            delete_error("Environment not created or corrupted!")
            return 2

        if interactive_delete:
            no_option = "no"
            value = raw_input(_("Delete Environment? [%(default)s]> ",
                                default=no_option)).strip() or no_option
            # Ask again if we want to delete the env!
            value = value.lower() in get_true_values()
            if not value:
                printout(_("Delete Canceled!"))
                return

        # Delete it!
        printout(_("Starting Delete Process"))
        self.__env.delete()

        # Close environment!
        self.__env.shutdown()

        # It's deleted, so purge it!
        printout(_(" Purge env directory %(purge_dir)s", purge_dir=self.envname))
        purge_dir(self.envname)
        printout(_("Environment successfully deleted"))

#===============================================================================
# Backup environment
#===============================================================================

    _help_backup = [
                       ('backup','backup an environment interactively'),
                       ('backup </path/to/project> <dest_file>','backup an environment')
                      ]

    def get_backup_data(self):
        returnvals = []
        # Basic instructions
        self.print_line()
        printout(_("""Starting Interactive environment backup at <%(envname)s>

Follow the instructions to backup the environment!""",
                   envname=self.envname))
        self.print_line()

        # Env path
        printout(_(""" Now enter the absolute path to the environment that you will backup."""))
        path = self.envname
        returnvals.append(raw_input(_("</path/to/project> [%(default)s]> ",
                                      default=path)).strip() or path)
        self.print_line()

        # Environment app
        printout(_(""" Destination file for tghe backup"""))
        dest = self.__env.backup_get_default_file_name()
        returnvals.append(raw_input(_("</dest/file> [%(default)s]> ",
                                      default=dest)).strip() or dest)

        return returnvals

    def do_backup(self, line):
        """
        backup the current env
        """
        def backup_error(msg):
            printerr(_("Backup for '%(env)s' failed:", env=self.envname),
                     "\n", msg)

        # Open env
        if not self.ceck_env(True):
            backup_error("Environment not created or corrupted!")
            return 2

        # get arguments
        backup_source = None
        backup_dest = None
        args = self.unicod_safe_split(line)

        if len(args) == 1 and not args[0]:
            returnvals = self.get_backup_data()
            backup_source, backup_dest = returnvals
        elif len(args) != 2:
            backup_error('Wrong number of arguments: %d' % len(args))
            return 2
        else:
            backup_source, backup_dest = args[:2]

        self.__env.backup(backup_source, backup_dest)

        # Close environment!
        self.__env.shutdown()

#===============================================================================
# Recover environment from backup
#===============================================================================
    _help_recover = [
                       ('recover','recover an environment interactively'),
                       ('recover </path/to/project> <backup_file>','recover an environment')
                      ]

    def get_recover_data(self):
        returnvals = []
        # Basic instructions
        self.print_line()
        printout(_("""Starting Interactive environment recovering at <%(envname)s>

Follow the instructions to recover environment!""",
                   envname=self.envname))
        self.print_line()

        # Env path
        printout(_(""" Now enter the absolute path where your environment should be created."""))
        path = self.envname
        returnvals.append(raw_input(_("</path/to/project> [%(default)s]> ",
                                      default=path)).strip() or path)
        self.print_line()

        # Environment app
        printout(_(""" Enter path where the backup file is locates"""))
        prompt = _("Backup File [</path/to/file>]> ")
        returnvals.append(raw_input(prompt).strip())

        return returnvals

    def recover_env(self, backupfile, dest_env=None, ):
        """
        recreate an env from a backup file
        """
        if zip_is_valid( backupfile ):
            if not dest_env:
                dest_env = self.envname
            self.print_line()
            printout(_("Starting recovery"))
            printout(_("\trecovery file: \t%(backupfile)s",backupfile=backupfile))
            printout(_("\tenv path: \t%(dest_env)s",dest_env=dest_env))

            #TODO: call self.__env.restored() on the recovered env!
        else:
            raise RecoverBackupFileError(_("Invalid zip file for recovery!"))

    def do_recover(self, line):
        """
        backup the current env
        """
        def recover_error(msg):
            printerr(_("Recover for '%(env)s' failed:", env=self.envname),
                     "\n", msg)

        # get arguments
        backup_file = None
        dest_env = None
        args = self.unicod_safe_split(line)
        if len(args) == 1 and not args[0]:
            returnvals = self.get_recover_data()
            dest_env, backup_file = returnvals
        elif len(args) != 2:
            recover_error('Wrong number of arguments: %d' % len(args))
            return 2
        else:
            dest_env, backup_file = args[:2]

        self.recover_env(backup_file, dest_env)

        # Close environment!
        self.__env.shutdown()

def main(args=None):
    admin = EnvAdmin()
    admin.main(args)

if __name__ == '__main__':
    pkg_resources.require('Concurrent==%s' % VERSION)
    sys.exit(main())
