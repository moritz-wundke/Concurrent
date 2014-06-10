# -*- coding: utf-8 -*-
"""
Some usefull base methods and helpers
"""
import errno
import locale
import os
import re
import sys
import time
import tempfile


try:
    # Python 2
    from urllib import quote, unquote, urlencode
except ImportError:
    # Python 3
    from urllib.parse import quote, unquote, urlencode

try:
    # Python 2
    from itertools import izip
except ImportError:
    # Python 3
    izip = zip

# our imports
from concurrent.core.util.texttransforms import *

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

def is_digit(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

def tprint(msg):
    """
    Print function used to not confuse newlines when printing from different therads
    """
    sys.stdout.write(msg + '\n')
    sys.stdout.flush()

# -- algorithmic utilities

DIGITS = re.compile(r'(\d+)')
def embedded_numbers(s):
    """Comparison function for natural order sorting based on
    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/214202."""
    pieces = DIGITS.split(s)
    pieces[1::2] = map(int, pieces[1::2])
    return pieces


# -- os utilities

class NaivePopen:
    """This is a deadlock-safe version of popen that returns an object with
    errorlevel, out (a string) and err (a string).

    The optional `input`, which must be a `str` object, is first written
    to a temporary file from which the process will read.
    
    (`capturestderr` may not work under Windows 9x.)

    Example: print Popen3('grep spam','\n\nhere spam\n\n').out
    """
    def __init__(self, command, input=None, capturestderr=None):
        outfile = tempfile.mktemp()
        command = '( %s ) > %s' % (command, outfile)
        if input:
            infile = tempfile.mktemp()
            tmp = open(infile, 'w')
            tmp.write(input)
            tmp.close()
            command = command + ' <' + infile
        if capturestderr:
            errfile = tempfile.mktemp()
            command = command + ' 2>' + errfile
        try:
            self.err = None
            self.errorlevel = os.system(command) >> 8
            outfd = file(outfile, 'r')
            self.out = outfd.read()
            outfd.close()
            if capturestderr:
                errfd = file(errfile,'r')
                self.err = errfd.read()
                errfd.close()
        finally:
            if os.path.isfile(outfile):
                os.remove(outfile)
            if input and os.path.isfile(infile):
                os.remove(infile)
            if capturestderr and os.path.isfile(errfile):
                os.remove(errfile)

# -- sys utils

def arity(f):
    return f.func_code.co_argcount

def get_last_traceback():
    import traceback
    from StringIO import StringIO
    tb = StringIO()
    traceback.print_exc(file=tb)
    return to_unicode(tb.getvalue())

def get_lines_from_file(filename, lineno, context=0):
    """Return `content` number of lines before and after the specified
    `lineno` from the file identified by `filename`.
    
    Returns a `(lines_before, line, lines_after)` tuple.
    """
    if os.path.isfile(filename):
        fileobj = open(filename, 'U')
        try:
            lines = fileobj.readlines()
            lbound = max(0, lineno - context)
            ubound = lineno + 1 + context


            charset = None
            rep = re.compile('coding[=:]\s*([-\w.]+)')
            for linestr in lines[0], lines[1]:
                match = rep.search(linestr)
                if match:
                    charset = match.group(1)
                    break

            before = [to_unicode(l.rstrip('\n'), charset)
                         for l in lines[lbound:lineno]]
            line = to_unicode(lines[lineno].rstrip('\n'), charset)
            after = [to_unicode(l.rstrip('\n'), charset) \
                         for l in lines[lineno + 1:ubound]]

            return before, line, after
        finally:
            fileobj.close()
    return (), None, ()

def safe__import__(module_name):
    """
    Safe imports: rollback after a failed import.
    
    Initially inspired from the RollbackImporter in PyUnit,
    but it's now much simpler and works better for our needs.
    
    See http://pyunit.sourceforge.net/notes/reloading.html
    """
    already_imported = sys.modules.copy()
    try:
        return __import__(module_name, globals(), locals(), [])
    except Exception as e:
        for modname in sys.modules.copy():
            if not already_imported.has_key(modname):
                del(sys.modules[modname])
        raise e

# -- setuptools utils

def get_module_path(module):
    # Determine the plugin that this component belongs to
    path = module.__file__
    module_name = module.__name__
    if path.endswith('.pyc') or path.endswith('.pyo'):
        path = path[:-1]
    if os.path.basename(path) == '__init__.py':
        path = os.path.dirname(path)
    base_path = os.path.splitext(path)[0]
    while base_path.replace(os.sep, '.').endswith(module_name):
        base_path = os.path.dirname(base_path)
        module_name = '.'.join(module_name.split('.')[:-1])
        if not module_name:
            break
    return base_path

def get_pkginfo(dist):
    """Get a dictionary containing package information for a package

    `dist` can be either a Distribution instance or, as a shortcut,
    directly the module instance, if one can safely infer a Distribution
    instance from it.
    
    Always returns a dictionary but it will be empty if no Distribution
    instance can be created for the given module.
    """
    import types
    if isinstance(dist, types.ModuleType):
        try:
            from pkg_resources import find_distributions
            module = dist
            module_path = get_module_path(module)
            for dist in find_distributions(module_path, only=True):
                if os.path.isfile(module_path) or \
                       dist.key == module.__name__.lower():
                    break
            else:
                return {}
        except ImportError:
            return {}
    import email
    attrs = ('author', 'author-email', 'license', 'home-page', 'summary',
             'description', 'version')
    info = {}
    def normalize(attr):
        return attr.lower().replace('-', '_')
    try:
        pkginfo = email.message_from_string(dist.get_metadata('PKG-INFO'))
        for attr in [key for key in attrs if key in pkginfo]:
            info[normalize(attr)] = pkginfo[attr]
    except IOError as e:
        err = 'Failed to read PKG-INFO file for %s: %s' % (dist, e)
        for attr in attrs:
            info[normalize(attr)] = err
    except email.Errors.MessageError as e:
        err = 'Failed to parse PKG-INFO file for %s: %s' % (dist, e)
        for attr in attrs:
            info[normalize(attr)] = err
    return info

# -- misc. utils

class Ranges(object):
    """
    Holds information about ranges parsed from a string
    
    >>> x = Ranges("1,2,9-15")
    >>> 1 in x
    True
    >>> 5 in x
    False
    >>> 10 in x
    True
    >>> 16 in x
    False
    >>> [i for i in range(20) if i in x]
    [1, 2, 9, 10, 11, 12, 13, 14, 15]
    
    Also supports iteration, which makes that last example a bit simpler:
    
    >>> list(x)
    [1, 2, 9, 10, 11, 12, 13, 14, 15]
    
    Note that it automatically reduces the list and short-circuits when the
    desired ranges are a relatively small portion of the entire set:
    
    >>> x = Ranges("99")
    >>> 1 in x # really fast
    False
    >>> x = Ranges("1, 2, 1-2, 2") # reduces this to 1-2
    >>> x.pairs
    [(1, 2)]
    >>> x = Ranges("1-9,2-4") # handle ranges that completely overlap
    >>> list(x)
    [1, 2, 3, 4, 5, 6, 7, 8, 9]

    The members 'a' and 'b' refer to the min and max value of the range, and
    are None if the range is empty:
    
    >>> x.a
    1
    >>> x.b
    9
    >>> e = Ranges()
    >>> e.a, e.b
    (None, None)

    Empty ranges are ok, and ranges can be constructed in pieces, if you
    so choose:
    
    >>> x = Ranges()
    >>> x.appendrange("1, 2, 3")
    >>> x.appendrange("5-9")
    >>> x.appendrange("2-3") # reduce'd away
    >>> list(x)
    [1, 2, 3, 5, 6, 7, 8, 9]

    ''Code contributed by Tim Hatch''
    """

    RE_STR = r"""\d+(?:[-:]\d+)?(?:,\d+(?:[-:]\d+)?)*"""
    
    def __init__(self, r=None):
        self.pairs = []
        self.a = self.b = None
        self.appendrange(r)

    def appendrange(self, r):
        """Add a range (from a string or None) to the current one"""
        if not r:
            return
        p = self.pairs
        for x in r.split(","):
            try:
                a, b = map(int, x.split('-', 1))
            except ValueError:
                a, b = int(x), int(x)
            if b >= a:
                p.append((a, b))
        self._reduce()

    def _reduce(self):
        """Come up with the minimal representation of the ranges"""
        p = self.pairs
        p.sort()
        i = 0
        while i + 1 < len(p):
            if p[i+1][0]-1 <= p[i][1]: # this item overlaps with the next
                # make the first include the second
                p[i] = (p[i][0], max(p[i][1], p[i+1][1])) 
                del p[i+1] # delete the second, after adjusting my endpoint
            else:
                i += 1
        if p:
            self.a = p[0][0] # min value
            self.b = p[-1][1] # max value
        else:
            self.a = self.b = None        

    def __iter__(self):
        """
        This is another way I came up with to do it.  Is it faster?
        
        from itertools import chain
        return chain(*[xrange(a, b+1) for a, b in self.pairs])
        """
        for a, b in self.pairs:
            for i in range(a, b+1):
                yield i

    def __contains__(self, x):
        """
        >>> 55 in Ranges()
        False
        """
        # short-circuit if outside the possible range
        if self.a is not None and self.a <= x <= self.b:
            for a, b in self.pairs:
                if a <= x <= b:
                    return True
                if b > x: # short-circuit if we've gone too far
                    break
        return False

    def __str__(self):
        """Provide a compact string representation of the range.
        
        >>> (str(Ranges("1,2,3,5")), str(Ranges()), str(Ranges('2')))
        ('1-3,5', '', '2')
        >>> str(Ranges('99-1')) # only nondecreasing ranges allowed
        ''
        """
        r = []
        for a, b in self.pairs:
            if a == b:
                r.append(str(a))
            else:
                r.append("%d-%d" % (a, b))
        return ",".join(r)

    def __len__(self):
        """The length of the entire span, ignoring holes.
        
        >>> (len(Ranges('99')), len(Ranges('1-2')), len(Ranges('')))
        (1, 2, 0)
        """
        if self.a is not None and self.b is not None:
            return self.b - self.a + 1
        else:
            return 0

def to_ranges(revs):
    """Converts a list of revisions to a minimal set of ranges.
    
    >>> to_ranges([2, 12, 3, 6, 9, 1, 5, 11])
    '1-3,5-6,9,11-12'
    >>> to_ranges([])
    ''
    """
    ranges = []
    begin = end = None
    def store():
        if end == begin:
            ranges.append(str(begin))
        else:
            ranges.append('%d-%d' % (begin, end))
    for rev in sorted(revs):
        if begin is None:
            begin = end = rev
        elif rev == end + 1:
            end = rev
        else:
            store()
            begin = end = rev
    if begin is not None:
        store()
    return ','.join(ranges)

def content_disposition(type, filename=None):
    """Generate a properly escaped Content-Disposition header"""
    if filename is not None:
        if isinstance(filename, unicode):
            filename = filename.encode('utf-8')
        type += '; filename=' + quote(filename, safe='')
    return type

def partition(iterable, order=None):
    result = {}
    if order is not None:
        for key in order:
            result[key] = []
    for item, category in iterable:
        result.setdefault(category, []).append(item)
    if order is None:
        return result
    return [result[key] for key in order]
