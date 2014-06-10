# -*- coding: utf-8 -*-
"""
Pickling of python instances
"""
from concurrent.core.components.component import Component, implements
from concurrent.core.config.config import IntItem, ConfigItem
from concurrent.core.application.api import IPickler
from concurrent.core.util.cryptohelper import CryptoHelper
from concurrent.core.transport.pyjsonrpc.rpcerror import JsonRpcError, jsonrpcerrors
from concurrent.core.exceptions.baseerror import ErrorCodeMap

# Import cPickle over pickle (python 2.7+ and 3+ compatible)
try: import cPickle as pickle
except ImportError: import pickle
import gzip
import base64

class PickleException(JsonRpcError):
    code = ErrorCodeMap.PickleException
    message = u"Failed to pickle a remote object"
    
jsonrpcerrors[PickleException.code] = PickleException

class UnpickleException(JsonRpcError):
    code = ErrorCodeMap.UnpickleException
    message = u"Failed to unpickle a remote object"
    
jsonrpcerrors[UnpickleException.code] = UnpickleException


class Pickler(Component):
    implements(IPickler)
    """
    Class responsible for pickling and unpickling objects
    """
    pickle_protocol = IntItem('pickler', 'protocol', pickle.HIGHEST_PROTOCOL,
        """Protocol used when pickling, by default pickle.HIGHEST_PROTOCOL""")
    
    secret = ConfigItem('pickler', 'secret', 'JhTv535Vg385V',
        """Default salt used on decrypting encrypting a pickle""")
    
    # salt size in bytes
    salt_size = IntItem('pickler', 'salt_size', 16,
        """Size of the salt used in the encryption process""")
    
    # number of iterations in the key generation
    num_iterations = IntItem('pickler', 'num_iterations', 20,
        """Number of iterations used in the key generation""")
    
    # the size multiple required for AES
    aes_padding = IntItem('pickler', 'aes_padding', 16,
        """Padding used for AES encryption""")
    
    def __init__(self):
        super(Pickler, self).__init__()        
        self.crypto_helper = CryptoHelper(self.salt_size, self.num_iterations, self.aes_padding)
        
        if self.secret == Pickler.secret.default.decode('utf-8'):
            self.log.warn("Pickler using default secret, please setup you own to avoid security vulnerabilities!")

    def pickle_f(self, fname, obj):
        """
        picke an object into a file
        """
        try:
            pickle.dump(obj=obj, file=gzip.open(fname, "wb"), protocol=self.pickle_protocol)
        except:
            raise PickleException()
    
    def unpickle_f(self, fname):
        """
        Unpicke an object from a file
        """
        try:
            return pickle.load(gzip.open(fname, "rb"))
        except:
            raise UnpickleException()
    
    def pickle_s(self, obj):
        """
        pickle an object and return the pickled string
        """
        try:
            return pickle.dumps(obj, protocol=self.pickle_protocol)
        except:
            raise PickleException()
        
    def pickle_encode_s(self, obj):
        """
        Encode a pickled object
        """
        try:
            return base64.b64encode(self.crypto_helper.encrypt(self.pickle_s(obj), self.secret))
        except:
            raise PickleException()
    
    def unpickle_s(self, pickle_string):
        """
        unpickle a string and return an object
        """
        try:
            return pickle.loads(pickle_string)
        except:
            raise UnpickleException()
    
    def unpickle_decode_s(self, pickle_string):
        """
        Unpickle a base64 string and return an object
        """
        try:
            return self.unpickle_s(self.crypto_helper.decrypt(base64.b64decode(pickle_string), self.secret))
        except:
            raise UnpickleException()
    