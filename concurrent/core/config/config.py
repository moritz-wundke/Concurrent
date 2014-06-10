# -*- coding: utf-8 -*-
"""
Config Sybsystem. Features hot reloading of configs and propagation
within the environment
"""
import os
try:
    # Python 2
    from ConfigParser import ConfigParser
except ImportError:
    # Python 3
    from configparser import ConfigParser
from copy import deepcopy
from concurrent.core.exceptions.baseerror import BaseError
from concurrent.core.util.texttransforms import to_unicode, CRLF, _
from concurrent.core.components.component import ExtensionPoint

__all__ = ['BaseConfigError','ConfigHandle','ConfigSection','ConfigItem','BoolItem',
           'IntItem','PathItem','ListItem','ExtensionPointItem']

# These values represents TRUE values for us
_TRUERS = [True,'true','ja','si','yes','on','enabled',1,'y']

# File name of our ini
_INI_FILENAME = 'env.ini'

def get_true_values():
    return _TRUERS

class BaseConfigError(BaseError):
    """
    Base error class for config related errors
    """
    title="[Config Error]"

class ConfigHandle(object):
    """
    Config parser that represents a config handle (file or memory). 
    """
    def __init__(self, filename):
        # Init Members
        self.filename = filename
        self._base_filename = None              
        self.based_on = None       
        self._lastmodified = 0
        self._sections = {}
        self._old_sections = {}
        
        # create parser
        self.parser = ConfigParser()
        
        # intial parse
        self.conditional_parse()

#===============================================================================
# Magic methods
#===============================================================================

    def __getitem__(self, section):
        """
        Find and return section that matches with `section`
        """
        if section not in self._sections:
            self._sections[section] = ConfigSection(self, section)
        return self._sections[section]
    
    def __contains__(self, section):
        """
        returns true if `section` is in the section list
        """
        return section in self.sections()
    
    def __repr__(self):
        """
        Human readable string to represent the file
        """
        return '<%s %r>' % (self.__class__.__name__, self.filename)

#===============================================================================
# Config Stuff
#===============================================================================
    
    def get(self, section, name, default=''):
        """
        Get a config item from a section. If no value is specified return default.
        """
        return self[section].get(name, default)

    def get_bool(self, section, name, default=''):
        """
        Get an item as a bool value.
        """
        return self[section].getbool(name, default)

    def get_int(self, section, name, default=''):
        """
        Get an item as an integer value.
        """
        return self[section].getint(name, default)

    def getlist(self, section, name, default='', sep=',', trim_empty=True):
        """
        Get a list of an list-like item
        """
        return self[section].getlist(name, default, sep, trim_empty)

    def get_path(self, section, name, default=''):
        """
        get an item as an absolute path
        """
        return self[section].getpath(name, default)

    def set(self, section, name, value):
        """
        Set a value. Needs to be saved to be persistent!
        """
        self[section].set(name, value)
        
    def remove(self, section, name):
        """
        remove an item
        """
        if self.parser.has_section(section):
            self.parser.remove_option(section, name)


    def defaults(self):
        """
        Return dictionary of default values
        """
        defaults = {}
        for (section, name), option in ConfigItem.reg_dict.items():
            defaults.setdefault(section, {})[name] = option.default
        return defaults

    def sections(self):
        """
        get a list of section names from our self and any one we're based on
        """
        sections = set(self.parser.sections())
        if self.based_on:
            sections.update(self.based_on.sections())
        else:
            sections.update(self.defaults().keys())
        return sorted(sections)
    
    def items(self, section):
        """
        Return a list of `(name, value)` tuples for every item in the
        specified section.
        """
        return self[section].items()
    
    def has_item(self, section, name):
        """
        return True if the specified item exists in the section
        """
        if self.parser.has_section(section):
            if name in self.parser.options(section):
                return True
        if self.based_on:
            return self.based_on.has_option(section, name)
        else:
            return (section, name) in ConfigItem.reg_dict
        
    def conditional_parse(self):
        """
        Will parse the filename in case some has been changed. Takes in account any config
        file this one is based on!
        """
        if not self.is_file_valid():
            return False
        
        """
        Has this file been modified?
        """
        changed = False
        modiftime = os.path.getmtime(self.filename)
        if modiftime > self._lastmodified:
            self.parser._sections = {}
            self.parser.read(self.filename)
            self._lastmodified = modiftime
            self._old_sections = deepcopy(self.parser._sections)
            changed = True

        if self.parser.has_option('baseon', 'file'):
            filename = self.parser.get('baseon', 'file')
            if not os.path.isabs(filename):
                filename = os.path.join(os.path.dirname(self.filename),
                                        filename)
            if not self.based_on or self.parent.filename != filename:
                self.based_on = ConfigHandle(filename)
                self.based_on._base_filename = self._base_filename \
                                                or self.filename
                changed = True
            else:
                changed |= self.based_on.conditional_parse()
        elif self.based_on:
            changed = True
            self.based_on = None

        return changed
        
    def save(self):
        """
        Save current sections and items. This will make them persisten!
        """
        if not self.filename:
            return

        # Only save options that differ from the defaults
        sections = []
        for section in self.sections():
            options = []
            for option in self[section]:
                default = None
                if self.based_on:
                    default = self.based_on.get(section, option)
                current = self.parser.has_option(section, option) and \
                          to_unicode(self.parser.get(section, option))
                if current is not False and current != default:
                    options.append((option, current))
            if options:
                sections.append((section, sorted(options)))

        try:
            fileobj = open(self.filename, 'w')
            try:
                fileobj.write('# -*- coding: utf-8 -*-\n\n')
                for section, options in sections:
                    fileobj.write('[%s]\n' % section)
                    for key, val in options:
                        if key in self[section].overridden:
                            fileobj.write('# %s = <baseon>\n' % key)
                        else:
                            val = val.replace(CRLF, '\n').replace('\n', '\n ')
                            fileobj.write('%s = %s\n' % (key,
                                                         val.encode('utf-8')))
                    fileobj.write('\n')
            finally:
                fileobj.close()
            self._old_sections = deepcopy(self.parser._sections)
        except Exception:
            # Revert all changes to avoid inconsistencies
            self.parser._sections = deepcopy(self._old_sections)
            raise
    
    def is_file_valid(self):
        """
        returns true if the current config file is valid or not
        """
        return self.filename and os.path.isfile(self.filename) \
           and os.access(self.filename, os.W_OK)
               
    def stamp(self):
        """
        Stamps the LastModified time on the file
        """
        if self.is_file_valid():
            os.utime(self.filename, None)

class ConfigSection(object):
    """
    Objects that represents a config section
    """
    __slots__ = ['config', 'name', 'overridden']

    def __init__(self, config, name):
        self.config = config
        self.name = name
        self.overridden = {}

    def __contains__(self, name):
        if self.config.parser.has_option(self.name, name):
            return True
        if self.config.based_on:
            return name in self.config.based_on[self.name]
        return ConfigItem.reg_dict.has_key((self.name, name))

    def __iter__(self):
        options = set()
        if self.config.parser.has_section(self.name):
            for option in self.config.parser.options(self.name):
                options.add(option.lower())
                yield option
        if self.config.based_on:
            for option in self.config.based_on[self.name]:
                if option.lower() not in options:
                    yield option
        else:
            for section, option in ConfigItem.reg_dict.keys():
                if section == self.name and option.lower() not in options:
                    yield option

    def __repr__(self):
        """
        Human readable string of this section
        """
        return '<Section [%s]>' % (self.name)

    def get(self, name, default=''):
        """
        Get a plain item value
        """
        if self.config.parser.has_option(self.name, name):
            value = self.config.parser.get(self.name, name)
        elif self.config.based_on:
            value = self.config.based_on[self.name].get(name, default)
        else:
            option = ConfigItem.reg_dict.get((self.name, name))
            if option:
                value = option.default or default
            else:
                value = default
        if not value:
            return u''
        elif isinstance(value, basestring):
            return to_unicode(value)
        else:
            return value

    def get_bool(self, name, default=''):
        """
        Return the value of the specified item as bool.
        """
        value = self.get(name, default)
        if isinstance(value, basestring):
            value = value.lower() in get_true_values()
        return bool(value)

    def get_int(self, name, default=''):
        """
        Return the value of the specified item as integer.
        
        @raise BaseConfigError: if value is not an integer
        """
        value = self.get(name, default)
        if not value:
            return 0
        try:
            return int(value)
        except ValueError:
            raise BaseConfigError(_('[%(section)s] %(entry)s: expected integer, got %(value)s', section=self.name, entry=name, value=repr(value)))
    
    def get_float(self, name, default=''):
        """
        Return the value of the specified item as float.
        
        @raise BaseConfigError: if value is not an float
        """
        value = self.get(name, default)
        if not value:
            return 0
        try:
            return float(value)
        except ValueError:
            raise BaseConfigError(_('[%(section)s] %(entry)s: expected float, got %(value)s', section=self.name, entry=name, value=repr(value)))
        
    def get_list(self, name, default='', sep='|', trim_empty=False):
        """
        Return a list of values that are separated by default with '|'.
                
        `trim_empty` can be used to trim empty elements.
        """
        value = self.get(name, default)
        if not value:
            return []
        if isinstance(value, basestring):
            items = [item.strip() for item in value.split(sep)]
        else:
            items = list(value)
        if trim_empty:
            items = filter(None, items)
        return items

    def get_path(self, name, default=''):
        """
        Get the relative path of the file from where the item was reed:
        """
        if self.config.parser.has_option(self.name, name):
            path = self.config.parser.get(self.name, name)
            if not path:
                return default
            if not os.path.isabs(path):
                path = os.path.join(os.path.dirname(self.config.filename),
                                    path)
            return os.path.normcase(os.path.realpath(path))
        elif self.config.based_on:
            return self.config.based_on[self.name].getpath(name, default)
        else:
            base = self.config._base_filename or self.config.filename
            path_opt = ConfigItem.reg_dict.get((self.name, name), None)
            path = path_opt and path_opt.default or default
            if path and not os.path.isabs(path):
                path = os.path.join(os.path.dirname(base), path)
            return path
    
    def get_host(self, name, default='localhost:80'):
        """
        Get a host tuple in form of (host,port)
        """
        value = self.get(name, default)
        if not value:
            return ('localhost',80)
        items = [item.strip() for item in value.split(':')]
        if len(items) == 2:
            try:
                items[1] = int(items[1])
            except ValueError:
                raise BaseConfigError(_('[%(section)s] %(entry)s: expected integer port number, got %(value)s', section=self.name, entry=name, value=repr(value)))
            return tuple(items)
        raise BaseConfigError(_('[%(section)s] %(entry)s: expected url in form of host:port, got %(value)s', section=self.name, entry=name, value=repr(value)))

    def items(self):
        """Return items in form of `(name, value)` tuples."""
        for name in self:
            yield name, self.get(name)

    def set(self, name, value):
        """
        Change a config value. Needs to be saved before it will be persistent.
        """
        if not self.config.parser.has_section(self.name):
            self.config.parser.add_section(self.name)
        if value is None:
            self.overridden[name] = True
            value = ''
        else:
            value = to_unicode(value).encode('utf-8')
        return self.config.parser.set(self.name, name, value)

class ConfigItem(object):
    """
    A config item is a (name,value) pair in a section uded by a config handle
    """
    
    """
    Method used for subclassed to get the items value :P
    """
    access_method = ConfigSection.get
    
    """
    We have to register every new item instance in our class member holder, so it's globally accessable
    """
    reg_dict = {}

    def __init__(self, section_name, item_name, default_value=None, doc_string=''):
        """        
        Create an config item
        """
        self.section = section_name
        self.name = item_name
        self.default = default_value
        self.reg_dict[(self.section, self.name)] = self
        self.__doc__ = doc_string

    def __get__(self, instance, owner):
        """
        instance can be none or a section (to get the cofnig file)
        """
        if instance is None:
            return self
        config = getattr(instance, 'config', None)
        if config and isinstance(config, ConfigHandle):
            section = config[self.section]
            value = self.access_method(section, self.name, self.default)
            return value
        return None

    def __set__(self, instance, value):
        """
        Default config object will raise an attribute error (never implemented)
        """
        raise AttributeError('can\'t set attribute: No method implemented!')

    def __repr__(self):
        """
        Human readable string for the item
        """
        return '<%s [%s] "%s">' % (self.__class__.__name__, self.section,self.name)

class BoolItem(ConfigItem):
    """
    Boolean item
    """
    access_method = ConfigSection.get_bool


class IntItem(ConfigItem):
    """
    Integer item
    """
    access_method = ConfigSection.get_int

class FloatItem(ConfigItem):
    """
    Float item
    """
    access_method = ConfigSection.get_float
    
class HostItem(ConfigItem):
    """
    Host item
    """
    access_method = ConfigSection.get_host

class ListItem(ConfigItem):
    """
    A list
    """

    def __init__(self, section, name, default=None, sep=',', keep_empty=False,
                 doc=''):
        ConfigItem.__init__(self, section, name, default, doc)
        self.sep = sep
        self.keep_empty = keep_empty

    def accessor(self, section, name, default):
        return section.get_list(name, default, self.sep, self.keep_empty)

class PathItem(ConfigItem):
    """
    An item representing a aboslute path
    """
    access_method = ConfigSection.get_path

class ExtensionPointItem(ConfigItem):
    """
    Item that represents an extension point
    """
    def __init__(self, section, name, interface, default=None, doc=''):
        ConfigItem.__init__(self, section, name, default, doc)
        self.CachedExtentionPoint = ExtensionPoint(interface)

    def __get__(self, instance, owner):
        if instance is None:
            return self
        value = ConfigItem.__get__(self, instance, owner)
        for impl in self.CachedExtentionPoint.extensions(instance):
            if impl.__class__.__name__ == value:
                return impl
        raise AttributeError('Cannot find an implementation of the "%s" '
                             'interface named "%s".  Please update the option '
                             '%s.%s in %s.'
                             % (self.CachedExtentionPoint.interface.__name__, value,
                                self.section, self.name, _INI_FILENAME))

class ExtensionPointListItem(ListItem):
    """
    Return a list of components implementing a specific interface. If 'include_mising'
    is True all components implementing the interface are returned, with those specified 
    in the config item first.
    """

    def __init__(self, section, name, interface, default=None,
                 include_missing=True, doc=''):
        ListItem.__init__(self, section, name, default, doc=doc)
        self.CachedExtentionPoint = ExtensionPoint(interface)
        self.include_missing = include_missing

    def __get__(self, instance, owner):
        if instance is None:
            return self
        order = ListItem.__get__(self, instance, owner)
        components = []
        for impl in self.CachedExtentionPoint.extensions(instance):
            if self.include_missing or impl.__class__.__name__ in order:
                components.append(impl)

        def compare(x, y):
            x, y = x.__class__.__name__, y.__class__.__name__
            if x not in order:
                return int(y in order)
            if y not in order:
                return -int(x in order)
            return cmp(order.index(x), order.index(y))
        components.sort(compare)
        return components
