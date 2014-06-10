# -*- coding: utf-8 -*-
"""
Sample application using Concurrent to perform a reverse hash
"""

from setuptools import find_packages, setup

if __name__ == '__main__':
    setup(
        name='ConcurrentReverseMD5', version='0.1',
        packages=find_packages(exclude=['*.tests*']),
        entry_points = {
            'concurrent.components': [
                'samples.reversemd5 = concurrent.framework.samples.reversemd5.app',
            ],
        },
    )
