# -*- coding: utf-8 -*-
"""
usefull stuff for text conversations, unicode, tags, etc etc...
"""
import locale
import os
import sys
# Just for security, we are aiming Python 3
try:
    # Python 2
    from urllib import quote, quote_plus, unquote, urlencode
except ImportError:
    # Python 3
    from urllib.parse import quote, quote_plus, unquote, urlencode

try:
    import __builtin__ as builtins
except ImportError:
    import builtins


CRLF = '\r\n'

# -- Unicode

def to_unicode(text, charset=None):
    """Convert a `str` object to an `unicode` object.

    If `charset` is given, we simply assume that encoding for the text,
    but we'll use the "replace" mode so that the decoding will always
    succeed.
    If `charset` is ''not'' specified, we'll make some guesses, first
    trying the UTF-8 encoding, then trying the locale preferred encoding,
    in "replace" mode. This differs from the `unicode` builtin, which
    by default uses the locale preferred encoding, in 'strict' mode,
    and is therefore prompt to raise `UnicodeDecodeError`s.

    Because of the "replace" mode, the original content might be altered.
    If this is not what is wanted, one could map the original byte content
    by using an encoding which maps each byte of the input to an unicode
    character, e.g. by doing `unicode(text, 'iso-8859-1')`.
    """
    if not isinstance(text, str):
        if isinstance(text, Exception):
            # two possibilities for storing unicode strings in exception data:
            try:
                # custom __str__ method on the exception (e.g. PermissionError)
                # Python 3 uses str() while 2 used unicode()
                try:
                    return unicode(text)
                except NameError:
                    return str(text)
            except UnicodeError:
                # unicode arguments given to the exception (e.g. parse_date)
                return ' '.join([to_unicode(arg) for arg in text.args])
        try:
            return unicode(text)
        except NameError:
            return str(text)
    if charset:
        try:
            return unicode(text, charset, 'replace')
        except NameError:
            return str(text)
    else:
        try:
            try:
                return unicode(text, 'utf-8')
            except NameError:
                return str(text, 'utf-8')
        except UnicodeError:
            try:
                return unicode(text, locale.getpreferredencoding(), 'replace')
            except NameError:
                return str(text, locale.getpreferredencoding(), 'replace')

def exception_to_unicode(err, traceback=""):
    """
    Turn an exception to a unicode string
    """
    message = '%s: %s' % (err.__class__.__name__, to_unicode(err))
    if traceback:
        from concurrent.core.util.utils import get_last_traceback
        traceback_only = get_last_traceback().split('\n')[:-2]
        message = ('\n%s\n%s' % (to_unicode('\n'.join(traceback_only)),
            message))
    return message

def unicode_quote(value, safe='/'):
    """A unicode aware version of urllib.quote"""
    return quote(value.encode('utf-8'), safe)

def unicode_quote_plus(value):
    """A unicode aware version of urllib.quote"""
    return quote_plus(value.encode('utf-8'))

def unicode_unquote(value):
    """A unicode aware version of urllib.unquote.

    Take `str` value previously obtained by `unicode_quote`.
    """
    return unquote(value).decode('utf-8')

def unicode_urlencode(params):
    """A unicode aware version of urllib.urlencode"""
    if isinstance(params, dict):
        params = params.items()
    return urlencode([(k, isinstance(v, unicode) and v.encode('utf-8') or v)
                      for k, v in params])

def to_utf8(text, charset='iso-8859-15'):
    """Convert a string to UTF-8, assuming the encoding is either UTF-8, ISO
    Latin-1, or as specified by the optional `charset` parameter.
    """
    try:
        # Do nothing if it's already utf-8
        try:
            unicode(text, 'utf-8')
        except NameError:
            str(text, 'utf-8')
        return text
    except UnicodeError:
        try:
            # Use the user supplied charset if possible
            try:
                u_string = unicode(text, charset)
            except NameError:
                u_string = str(text, charset)
        except UnicodeError:
            # This should always work
            try:
                u_string = unicode(text, 'iso-8859-15')
            except NameError:
                u_string = str(text, 'iso-8859-15')
        return u_string.encode('utf-8')

def console_print(out, *args, **kwargs):
    """
    Low level console print method
    """
    cons_charset = getattr(out, 'encoding', None)
    # Windows returns 'cp0' to indicate no encoding
    if cons_charset in (None, 'cp0'):
        cons_charset = 'utf-8'
    out.write(' '.join([to_unicode(a).encode(cons_charset, 'replace')
                        for a in args]))
    if kwargs.get('newline', True):
        out.write('\n')

def raw_input(prompt):
    """
    Catch raw input from the console
    """
    console_print(sys.stdout, prompt, newline=False)
    return to_unicode(builtins.raw_input(), sys.stdin.encoding)

# -- Console text output formating

def printout(*args):
    """
    Print to the standard out
    """
    console_print(sys.stdout, *args)

def printerr(*args):
    """
    Print to the standard err
    """
    console_print(sys.stderr, *args)

def print_table(data, headers=None, sep='  ', out=None):
    if out is None:
        out = sys.stdout
    charset = getattr(out, 'encoding', None) or 'utf-8'
    data = list(data)
    if headers:
        data.insert(0, headers)
    elif not data:
        return

    num_cols = len(data[0]) # assumes all rows are of equal length
    col_width = []
    for idx in range(num_cols):
        col_width.append(max([len(unicode(d[idx] or '')) for d in data]))

    out.write('\n')
    for ridx, row in enumerate(data):
        for cidx, cell in enumerate(row):
            if headers and ridx == 0:
                sp = ('%%%ds' % len(sep)) % ' '  # No separator in header
            else:
                sp = sep
            if cidx + 1 == num_cols:
                sp = '' # No separator after last column

            line = (u'%%-%ds%s' % (col_width[cidx], sp)) % (cell or '')
            if isinstance(line, unicode):
                line = line.encode(charset, 'replace')
            out.write(line)

        out.write('\n')
        if ridx == 0 and headers:
            out.write(''.join(['-' for x in xrange(0, len(sep) * cidx +
                                                      sum(col_width))]))
            out.write('\n')

    out.write('\n')

def shorten_line(text, maxlen=75):
    if len(text or '') < maxlen:
        return text
    cut = max(text.rfind(' ', 0, maxlen), text.rfind('\n', 0, maxlen))
    if cut < 0:
        cut = maxlen
    return text[:cut] + ' ...'

def wrap(t, cols=75, initial_indent='', subsequent_indent='',
         linesep=os.linesep):
    try:
        import textwrap
        t = t.strip().replace('\r\n', '\n').replace('\r', '\n')
        wrapper = textwrap.TextWrapper(cols, replace_whitespace=0,
                                       break_long_words=0,
                                       initial_indent=initial_indent,
                                       subsequent_indent=subsequent_indent)
        wrappedLines = []
        for line in t.split('\n'):
            wrappedLines += wrapper.wrap(line.rstrip()) or ['']
        return linesep.join(wrappedLines)

    except ImportError:
        return t

def obfuscate_email_address(address):
    if address:
        at = address.find('@')
        if at != -1:
            return address[:at] + u'@\u2026' + \
                   (address[-1] == '>' and '>' or '')
    return address

# -- Conversion

def cool_size(size, format='%.1f'):
    if size is None:
        return ''

    jump = 512
    if size < jump:
        return '%d bytes' % size

    units = ['KB', 'MB', 'GB', 'TB']
    i = 0
    while size >= jump and i < len(units):
        i += 1
        size /= 1024.

    return (format + ' %s') % (size, units[i - 1])

def expandtabs(s, tabstop=8, ignoring=None):
    if '\t' not in s: return s
    if ignoring is None: return s.expandtabs(tabstop)

    outlines = []
    for line in s.split('\n'):
        if '\t' not in line:
            outlines.append(line)
            continue
        p = 0
        s = []
        for c in line:
            if c == '\t':
                n = tabstop-p%tabstop
                s.append(' '*n)
                p+=n
            elif not ignoring or c not in ignoring:
                p += 1
                s.append(c)
            else:
                s.append(c)
        outlines.append(''.join(s))
    return '\n'.join(outlines)

def gettext_fake(string, **kwargs):
    retval = string
    if kwargs:
        retval %= kwargs
    return retval
N_ = gettext_fake
gettext = _ = gettext_fake

def ngettextp_fake(singular, plural, num, **kwargs):
    if num == 1:
        retval = singular
    else:
        retval = plural
    kwargs.setdefault('num', num)
    return retval % kwargs
ngettext = ngettextp_fake
