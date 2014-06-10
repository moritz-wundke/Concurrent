# -*- coding: utf-8 -*-
"""
Sample application using Concurrent to perform a DNA curve analysis
"""

from setuptools import find_packages, setup

if __name__ == '__main__':
    setup(
        name='DNACurve', version='0.1',
        packages=find_packages(exclude=['*.tests*']),
        entry_points = {
            'concurrent.components': [
                'samples.dnacurve = concurrent.framework.samples.dnacurve.app',
            ],
        },
    )
