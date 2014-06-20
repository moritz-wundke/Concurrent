# Copyright (C) 2014 Moritz Wundke
# Author: Moritz Wundke

import os, sys
from setuptools import setup, find_packages
from distutils.extension import Extension
import imp

# scan the root directory for extension files, converting
# them to extension names in dotted notation
def scandir(root_dir, files=[], extension='.pyx'):
    """
    Scan a directory and return a list of cython source files
    """
    for filename in os.listdir(root_dir):
        path = os.path.join(root_dir, filename)
        if os.path.isfile(path) and path.endswith(extension):
            files.append(path.replace(os.path.sep, ".")[:-len(extension)])
        elif os.path.isdir(path):
            scandir(path, files)
    return files


# generate an Extension object from its dotted name
def makeExtension(extName, extension='.pyx'):
    """
    Create extension points which are later compiled into C
    code files.
    """
    extPath = extName.replace(".", os.path.sep)+extension
    return Extension(
        extName,
        [extPath],
        include_dirs = ["."],   # adding the '.' to include_dirs is CRUCIAL!! see https://github.com/cython/cython/wiki/PackageHierarchy
        extra_compile_args = ["-O3", "-Wall"],#, "-Werror"],
        extra_link_args = ['-g'],
        libraries = [],
        )

def generateExtensions(extName, extension='.pyx'):
    """
    Create all extensions for a given package
    """
    # get the list of extensions
    extNames = scandir(extName, [], extension)
    # and build up the set of Extension objects
    return [makeExtension(name, extension) for name in extNames]

CLASSIFIERS = """\
Development Status :: 5 - Production/Stable
Intended Audience :: Science/Research
Intended Audience :: Developers
License :: OSI Approved
Programming Language :: C
Programming Language :: Python
Topic :: Software Development
Topic :: Scientific/Engineering
Operating System :: Microsoft :: Windows
Operating System :: POSIX
Operating System :: Unix
Operating System :: MacOS
Topic :: Software Development :: Application Framework'
"""

REQUIEREMENTS = [
          'setuptools>=3.4.4'
        , 'bunch>=1.0.1'
        , 'Cython>=0.20.1'
        , 'docutils>=0.11'
        , 'MarkupSafe>=0.21'
        , 'nose>=1.3.3'
        , 'numpy>=1.8.1'
        , 'pycrypto>=2.6.1'
        , 'pytz>=2014.2'
        # , 'pywin32>=218.5' Only used on windows
        , 'rsa>=3.1.4'
        , 'simplejson>=3.4.1'
        , 'SQLAlchemy>=0.9.4'
        , 'ujson>=1.33'
        , 'web.py>=0.37'
        , 'pyzmq>=14.3.0'
        , 'pyasn1>=0.1.3'
        # , 'python-jsonrpc>=0.3.4' We use it but with our own modifications!
        # , 'sphinx_bootstrap_theme>=0.4.0'  only for documentation :P
        # Do we really need this one? This is more a client side module...
        # sudo apt-get build-dep python-matplotlib
        # Windows requires GnuWin32 libs first
        , 'matplotlib>=1.3.1' # Used for the samples
    ]
 

ENTRY_POINTS = """\
[console_scripts]
con-admin = concurrent.core.environment.envadmin:main

[concurrent.components]
concurrent.core.environment.envadmin = concurrent.core.environment.envadmin
concurrent.core.application.application = concurrent.core.application.application
concurrent.core.application.pickler = concurrent.core.application.pickler
concurrent.core.db.dbengines = concurrent.core.db.dbengines
concurrent.core.async.task = concurrent.core.async.task
concurrent.framework.nodes.slavenode = concurrent.framework.nodes.slavenode
concurrent.framework.nodes.masternode = concurrent.framework.nodes.masternode
concurrent.framework.nodes.applicationnode = concurrent.framework.nodes.applicationnode
concurrent.framework.samples.dnacurve.app = concurrent.framework.samples.dnacurve.app
concurrent.framework.samples.reversemd5.app = concurrent.framework.samples.reversemd5.app
concurrent.framework.samples.mandlebrot.app = concurrent.framework.samples.mandlebrot.app
concurrent.framework.samples.expensive.app = concurrent.framework.samples.expensive.app
"""
def setup_package():
    
    cmdclass = { }
    ext_modules = [ ]
    
    if 'build_ext' in sys.argv:
        ext_modules += generateExtensions('concurrent', '.pyx')
        from Cython.Compiler.Main import default_options
        default_options['emit_linenums'] = True
        from Cython.Distutils import build_ext
        cmdclass.update({'build_ext': build_ext})
    else:
        ext_modules += generateExtensions('concurrent', '.c')

    # Get version info
    VERSION = imp.load_source('VERSION', 'VERSION')

    metadata = dict(
          name = 'Concurrent'
        , version = VERSION.VERSION_LONG
        , description = 'Concurrent Application Framework'
        , long_description=open('README.md').read()
        , author = 'Moritz Wundke'
        , author_email = 'b.thax.dcg@gmail.com'
        , maintainer = 'Moritz Wundke'
        , maintainer_email = 'b.thax.dcg@gmail.com'
        , license = 'MIT'
        , classifiers=[_f for _f in CLASSIFIERS.split('\n') if _f]
        , platforms = ["Windows", "Linux", "Solaris", "Mac OS-X", "Unix"]
        
        , url = "http://www.moritzwundke.com/"
        , download_url = "http://www.moritzwundke.com/"
        
        , cmdclass = cmdclass
        , ext_modules=ext_modules
        , packages = find_packages()
        , zip_safe = False
        , install_requires = REQUIEREMENTS
        , entry_points = ENTRY_POINTS
    )
    
    setup(**metadata)
    return
    

if __name__ == '__main__':
    setup_package()
