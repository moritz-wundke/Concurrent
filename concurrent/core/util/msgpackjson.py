# -*- coding: utf-8 -*-
"""
msgpackjson.py - JSON loads and dumps proxy defenitions and implemented using msgpack instead

Copyright (C) 2014, Moritz Wundke.
Released under MIT license.
"""

try:
    import msgpack
    import base64
    import gc
    
    def loads(data):
        gc.disable()
        result = msgpack.unpackb(base64.b64decode(data), use_list=False)
        gc.enable()
        return result
    
    def dumps(obj):
        gc.disable()
        result =  base64.b64encode(msgpack.packb(obj))
        gc.enable()
        return result
except:
    def loads(data):
        raise NotImplemented("msgpack missing! Please install Message Pack for python!")
    
    def dumps(obj):
        raise NotImplemented("msgpack missing! Please install Message Pack for python!")