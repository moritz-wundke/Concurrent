==========
Concurrent
==========

Distributed task system based on ZeroMQ and a trac [by Edgewall] like component architecture.

For more info visit the `project page <http://moritz-wundke.github.io/Concurrent/>`_

Code
====

All code is hosted on GitHub. The master branch features the latest stable release while the develop branch features the latest changes and features. Please note that the develop branch mai not be even usable.

Install
========

The easiest way to install concurrent is to download it's source package and just install it using pythons disctools::

    python setup.py build_ext
    python setup.py install

Make sure to have the python development headers installed, you also require a valid C compiler (See Setup section)

.. toctree::
   :maxdepth: 2

   README
   examples
   sidebar
   subdir/index

.. toctree::
   :maxdepth: 1

   HISTORY
   TODO

.. Disabled.
..    downloads

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
