# -*- coding: utf-8 -*-
"""
WSGI gzip middleware adapted from: http://www.evanfosmark.com/2008/12/python-wsgi-middleware-for-automatic-gzipping/
"""

from gzip import GzipFile
import StringIO

class Gzipper(object):
    """ WSGI middleware to wrap around and gzip all output.
        This automatically adds the content-encoding header.
    """
    def __init__(self, app, compresslevel=6):
        self.app = app
        self.compresslevel = compresslevel
 
    def __call__(self, environ, start_response):
        """ Do the actual work. If the host doesn't support gzip as a proper encoding,
            then simply pass over to the next app on the wsgi stack.
        """
        accept_encoding_header = environ.get("HTTP_ACCEPT_ENCODING", "")
        if(not self.client_wants_gzip(accept_encoding_header)):
                return self.app(environ, start_response)
 
        def _start_response(status, headers, *args, **kwargs):
            """ Wrapper around the original `start_response` function.
                The sole purpose being to add the proper headers automatically.
            """
            headers.append(("Content-Encoding", "gzip"))
            headers.append(("Vary", "Accept-Encoding"))
            return start_response(status, headers, *args, **kwargs)
 
        # Unfortunately, we can't gzip data chunk-by-chunk, so we need to join up whatever
        # is being sent out first. (Remember, WSGI apps return items which can be iterated.)
        data = "".join(self.app(environ, _start_response))
        return [self.gzip_string(data, self.compresslevel)]
    
    def parse_encoding_header(self, header):
        """ Break up the `HTTP_ACCEPT_ENCODING` header into a dict of
            the form, {'encoding-name':qvalue}.
        """
        encodings = {'identity':1.0}
     
        for encoding in header.split(","):
            if(encoding.find(";") > -1):
                encoding, qvalue = encoding.split(";")
                encoding = encoding.strip()
                qvalue = qvalue.split('=', 1)[1]
                if(qvalue != ""):
                    encodings[encoding] = float(qvalue)
                else:
                    encodings[encoding] = 1
            else:
                encodings[encoding] = 1
        return encodings
     
    def client_wants_gzip(self, accept_encoding_header):
        """ Check to see if the client can accept gzipped output, and whether
            or not it is even the preferred method. If `identity` is higher, then
            no gzipping should occur.
        """
        encodings = self.parse_encoding_header(accept_encoding_header)
     
        # Do the actual comparisons
        if('gzip' in encodings):
            return encodings['gzip'] >= encodings['identity']
     
        elif('*' in encodings):
            return encodings['*'] >= encodings['identity']
     
        else:
            return False
    
    def gzip_string(self, string, compression_level):
        """ The `gzip` module didn't provide a way to gzip just a string.
            Had to hack together this. I know, it isn't pretty.
        """
        fake_file = StringIO.StringIO()
        gz_file = GzipFile(None, 'wb', compression_level, fileobj=fake_file)
        gz_file.write(string)
        gz_file.close()
        return fake_file.getvalue()