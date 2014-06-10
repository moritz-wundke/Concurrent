# -*- coding: utf-8 -*-
"""
Base class every component used. A component is handled as a plugin.
The features of a plugin is defined by interfaces. Those interfaces will
force a component to resolve queries that come from the framework.
"""
from glob import glob
import imp
import pkg_resources
from pkg_resources import working_set, DistributionNotFound, VersionConflict, \
                          UnknownExtra
import os
import sys

from concurrent.core.util.texttransforms import exception_to_unicode

# We only load that one coz' it will be the only entrypoint of this module
__all__ = ['load_components']

def _enable_component(env, module):
    """Enable the given component by adding an entry to the configuration.
    TODO: This depends on how I'll finally create the config behavior of our environment :D
    """
    if module + '.*' not in env.config['components']:
        env.config['components'].set(module + '.*', 'enabled')

def load_eggs(entry_point_name):
    """Loader that loads any eggs on the search path and `sys.path`."""
    def _load_eggs(env, search_path, auto_enable=None):
        # Note that the following doesn't seem to support unicode search_path
        distributions, errors = working_set.find_plugins(
            pkg_resources.Environment(search_path)
        )
        for dist in distributions:
            env.log.debug('Adding plugin %s from %s', dist, dist.location)
            working_set.add(dist)

        def _log_error(item, e):
            ue = exception_to_unicode(e)
            if isinstance(e, DistributionNotFound):
                env.log.debug('Skipping "%s": ("%s" not found)', item, ue)
            elif isinstance(e, VersionConflict):
                env.log.error('Skipping "%s": (version conflict "%s")',
                              item, ue)
            elif isinstance(e, UnknownExtra):
                env.log.error('Skipping "%s": (unknown extra "%s")', item, ue)
            elif isinstance(e, ImportError):
                #env.log.error('Skipping "%s": (can\'t import "%s")', item, ue)
                print('Skipping "%s": (can\'t import "%s")' % ( item, ue) )
            else:
                env.log.error('Skipping "%s": (error "%s")', item, ue)

        for dist, e in errors.iteritems():
            _log_error(dist, e)
        for entry in working_set.iter_entry_points(entry_point_name):
            env.log.debug('Loading %s from %s', entry.name,
                          entry.dist.location)
            try:
                entry.load(require=True)
            except (ImportError, DistributionNotFound, VersionConflict,
                    UnknownExtra) as e:
                print(entry.module_name)
                _log_error(entry, e)
            else:
                if os.path.dirname(entry.dist.location) == auto_enable:
                    _enable_component(env, entry.module_name)
    return _load_eggs

def load_py_files():
    """Loader that look for Python source files in the plugins directories,
    which simply get imported, thereby registering them with the component
    manager if they define any components.
    """
    def _load_py_files(env, search_path, auto_enable=None):
        for path in search_path:
            plugin_files = glob(os.path.join(path, '*.py'))
            for plugin_file in plugin_files:
                try:
                    plugin_name = os.path.basename(plugin_file[:-3])
                    env.log.debug('Loading file plugin %s from %s' % \
                                  (plugin_name, plugin_file))
                    if plugin_name not in sys.modules:
                        module = imp.load_source(plugin_name, plugin_file)
                    if path == auto_enable:
                        _enable_component(env, plugin_name)
                except Exception as e:
                    env.log.error('Failed to load plugin from %s: %s',
                                  plugin_file,
                                  exception_to_unicode(e, traceback=True))
    return _load_py_files

def load_components(env, extra_path=None, loaders=(load_eggs('concurrent.components'),
                                                   load_py_files())):
    """Load all components found on the given search path."""
    plugins_dir = os.path.normcase(os.path.realpath(
        env.get_plugins_dir()
    ))    
    search_path = [plugins_dir]

    # add paths to our framework folders
    framework_dir = os.path.normcase(os.path.realpath(
        env.get_plugins_dir()
    ))  
    
    # if we got any extra path to be added, do this now!
    if extra_path:
        search_path += list(extra_path)
        
    # Load all component we can
    for loadfunc in loaders:
        loadfunc(env, search_path, auto_enable=plugins_dir)
