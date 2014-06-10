# -*- coding: utf-8 -*-
"""
Cryptographic helper
"""

import Crypto.Random
from Crypto.Cipher import AES
import hashlib
import base64

class CryptoHelper(object):
    """
    Crypto helper used in the framework
    """
    def __init__(self, salt_size, num_iterations, aes_padding):
        self.salt_size = salt_size
        self.num_iterations = num_iterations
        self.aes_padding = aes_padding

    def _generate_key(self, password, salt, iterations):
        assert iterations > 0
        key = password + salt
        for i in range(iterations):
            key = hashlib.sha256(key).digest()
        return key

    def _pad_text(self, text, multiple):
        extra_bytes = len(text) % multiple
        padding_size = multiple - extra_bytes
        padding = chr(padding_size) * padding_size
        padded_text = text + padding
        return padded_text

    def _unpad_text(self, padded_text):
        padding_size = ord(padded_text[-1])
        text = padded_text[:-padding_size]
        return text

    def encrypt(self, plaintext, password):
        plaintext = base64.b64encode(plaintext)
        password = base64.b64encode(password)
        salt = Crypto.Random.get_random_bytes(self.salt_size)    
        key = self._generate_key(password, salt, self.num_iterations)    
        cipher = AES.new(key, AES.MODE_ECB)    
        padded_plaintext = self._pad_text(plaintext, self.aes_padding)    
        ciphertext = cipher.encrypt(padded_plaintext)
        return salt + ciphertext    

    def decrypt(self, ciphertext, password):
        password = base64.b64encode(password)
        salt = ciphertext[0:self.salt_size]
        ciphertext_sans_salt = ciphertext[self.salt_size:]
        key = self._generate_key(password, salt, self.num_iterations)
        cipher = AES.new(key, AES.MODE_ECB)
        padded_plaintext = cipher.decrypt(ciphertext_sans_salt)
        return base64.b64decode(self._unpad_text(padded_plaintext))