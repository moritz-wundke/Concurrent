# -*- coding: utf-8 -*-
"""
Basic command line application
"""
import cmd
import locale
import os
import shlex
import sys

from concurrent.core.util.texttransforms import _, to_unicode, console_print
from concurrent.core.util.texttransforms import printerr, printout
from concurrent.core.exceptions.baseerror import BaseError


class CMD(cmd.Cmd):
    """
    Basic CMD application
    """

    # Definitions we need (see cmd.Cmd for more info)
    intro = ''
    doc_header = 'DEFINE HEADER'
    ruler = ''
    prompt = "CMD> "
    __env = None
    _date_format = '%Y-%m-%d'
    _datetime_format = '%Y-%m-%d %H:%M:%S'
    _date_format_hint = 'YYYY-MM-DD'

    def __init__(self, envdir=None):
        cmd.Cmd.__init__(self)
        self.interactive = False
        if envdir:
            self.env_set(os.path.abspath(envdir))
        self._permsys = None

        self.envname = ''

    def emptyline(self):
        pass

    def onecmd(self, line):
        """`line` may be a `str` or an `unicode` object"""
        try:
            if isinstance(line, str):
                if self.interactive:
                    encoding = sys.stdin.encoding
                else:
                    encoding = locale.getpreferredencoding() # sys.argv
                line = to_unicode(line, encoding)
            if self.interactive:
                line = line.replace('\\', '\\\\')
            rv = cmd.Cmd.onecmd(self, line) or 0
        except SystemExit:
            raise
        except BaseError as e:
            printerr(_("Command failed:"), e)
            rv = 2
        if not self.interactive:
            return rv

    def set_env(self, name, env=None):
        """
        Set a new env to be used
        """
        self.envname = name

    def print_interactive_header(self):
        printout(_("""[Generic CMD App]
Copyright (c) 2014 Moritz Wundke

Type:  '?' or 'help' for help on commands.
        """))

    def run(self):
        self.interactive = True
        self.print_interactive_header()
        self.cmdloop()

    def print_version(self):
        """
        Print version of app
        """
        printout(os.path.basename(sys.argv[0]), '0')

    def main(self, args=None):
        """
        Main entry point for this application
        """
        if args is None:
            args = sys.argv[1:]

        if len(args) > 0:
            if args[0] in ('-h', '--help', 'help'):
                return self.onecmd('help')
            elif args[0] in ('-v','--version'):
                self.print_version()
            else:
                env_path = os.path.abspath(args[0])
                try:
                    try:
                        unicode(env_path, 'ascii')
                    except NameError:
                        str(env_path, 'ascii')
                except UnicodeDecodeError:
                    printerr(_("non-ascii environment path '%(path)s' not "
                               "supported.", path=env_path))
                    sys.exit(2)
                self.set_env(env_path)
                if len(args) > 1:
                    s_args = ' '.join(["'%s'" % c for c in args[2:]])
                    command = args[1] + ' ' +s_args
                    return self.onecmd(command)
                else:
                    while True:
                        try:
                            self.run()
                        except KeyboardInterrupt:
                            self.do_quit('')
        else:
            while True:
                try:
                    self.run()
                except KeyboardInterrupt:
                    self.do_quit('')

#===============================================================================
# Miscs
#===============================================================================
    def print_line(self):
        """
        Print a line :P
        """
        printout(_("""--------------------------------------------------------------------------"""))

    def unicod_safe_split (self, argstr):
        """
        `argstr` is an `str` string
        """
        try:
            return [unicode(token, 'utf-8')
                    for token in shlex.split(argstr.encode('utf-8'))] or ['']
        except NameError:
            return [str(token, 'utf-8')
                    for token in shlex.split(argstr.encode('utf-8'))] or ['']

    def complete_word (self, text, words):
        return [a for a in words if a.startswith (text)]

    def print_help(cls, docs, stream=None):
        if stream is None:
            stream = sys.stdout
        if not docs: return
        for cmd, doc in docs:
            console_print(stream, ' * [%s]' % cmd, newline=False)
            console_print(stream, '\n   - %s' % doc, newline=True)
    print_help = classmethod(print_help)

#===============================================================================
# Commands - Help
#===============================================================================

    _help_help = [('help','Show help')]

    def all_docs(cls):
        return (
                cls._help_help +
                cls._help_quit
                )

    all_docs = classmethod(all_docs)

    def print_help_header(self):
        printout(_("Concurrent - Console application"))

    def print_usage_help(self):
        printout(_("Usage: <appname> </path/to/projenv> "
                   "[command [subcommand] [option ...]]\n")
            )
        printout(_("Invoking <appname> without command starts "
                   "interactive mode."))

    def do_help(self, line=None):
        self.print_help_header()
        arg = self.unicod_safe_split(line)
        if arg[0]:
            try:
                doc = getattr(self, "_help_" + arg[0])
                self.print_help(doc)
            except AttributeError:
                printerr(_("No documentation found for '%(cmd)s'", cmd=arg[0]))
        else:
            self.print_usage_help()
            self.print_help(self.all_docs())

#===============================================================================
# Commands - Exit (EOF or quit)
#===============================================================================

    _help_quit = [['quit', 'Exit']]
    _help_exit = _help_quit
    _help_EOF = _help_quit

    def do_quit(self, line):
        printout(_("\nSee you soon!"))
        sys.exit()

    # make aliasses for the others
    do_exit = do_quit
    do_EOF = do_quit
