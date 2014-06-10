try:
    distro = __import__('pkg_resources').get_distribution('Concurrent')
    __version__ = distro.version
    __key__ = distro.key
except ImportError:
    __version__ = 0
    __key__ = ''
__author__ = "Moritz Wundke"
__license__ = "MIT license"