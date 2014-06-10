# Copyright (C) 2014 Moritz Wundke
# Author: Moritz Wundke
# Contact: b.thax.dcg@gmail.com

"""Set of PI aproximations implemented in pure python, threaded python,
multiprocess python and cython. Used to benchmakr the differences between
all of them.
"""

# default module export
__all__ = [
    'recip_square',
    'approx_pi',
    'recip_square_pure',
    'approx_pi_pure',
    ]

# cython implementation
cimport cython

@cython.profile(False)
cdef inline double crecip_square(float i):
    """
    Inverse the square of

    Example:

    >>> crecip_square(4)
    6.25

    """
    return 1.0/(i**2)

def recip_square(i):
    """
    Pure python wrapper for c implementation
    """
    return crecip_square(i)

def approx_pi(int n):
    """
    Calculate an aproximation to pi using n iterations
    """
    cdef double val = 0.
    cdef int k
    for k in xrange(1,n+1):
        val += crecip_square(k)
    return (6 * val)**.5

# pure python implementation
def recip_square_pure(i):
    """
    Inverse the square of

    Example:

    >>> recip_square_pure(4)
    6.25

    """
    return 1./i**2

def approx_pi_pure(n):
    """
    Calculate an aproximation to pi using n iterations
    """
    val = 0.
    for k in range(1,n+1):
        val += recip_square_pure(k)
    return (6 * val)**.5
