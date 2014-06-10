# Concurrent #
A python concurrent framework based on a trac [by Edgewall] like component architecture

# Overview #

## Scientific modules ##
 * numpy
 * matplotlib
 * scipy
 * pandas

# Usage #

# Install #
The easiest way to install concurrent is to download it's source package and just install it using pythons disctools:

    python setup.py build_ext
    python setup.py install

Make sure to have the python development headers installed, you also require a valid C compiler (See Setup section)

# Contribute #

Documentation suing sphinx, execute the generate_api.sh script

make sure all cython modules are compiled, if not the documentation process will fail!

# Setup #

 * C compiler (GCC, VS, Clang, ...)
 * Python dev headers
 * sqlalchemy
 * setuptools
