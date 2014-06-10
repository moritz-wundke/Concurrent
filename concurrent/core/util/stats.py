# -*- coding: utf-8 -*-
"""
Simple stats helper handling min, max, avg and callnumber stats. The Stats class is thread safe using a ReadWrite lock
"""

from concurrent.core.async.threads import ReadWriteLock
from concurrent.core.util.singletonmixin import Singleton
from collections import defaultdict

import sys
import time
from bunch import Bunch

start_time = []

def time_push():
    """
    Push a start time mark
    """
    global start_time
    start_time.append(time.time())

def time_pop():
    """
    Calculate ellapsed time from the last push start mark
    """
    global start_time
    start = start_time.pop()
    if start >= 0:
        return time.time() - start
    return 0

class StatsGatherer(object):
    """
    Thread safe Stats gathere, handels average, min, max and call counts. Useful for benchmarking.
    
    Usage:
        
    # Just add a stat
    stats = Stats.getInstance()
    stats.add_avg('MyStat',1)
    
    # This will just give you a copy of the current stat
    print(stats.MyStat)
    {'avg':1,'min':1,'max':1,'n':1}
    """
    def __init__(self):
        object.__init__(self)     
        self.lock = ReadWriteLock()
        self._stats = defaultdict(self._default_stat)
    
    def _default_stat(self):
        return Bunch({'avg':0.0, 'min':sys.float_info.max, 'max':sys.float_info.min, 'n':0})
    
    def add_avg(self, stat, value=0):
        with self.lock.writelock:
            self._stats[stat].avg = ((self._stats[stat].avg * self._stats[stat].n) + value) / (self._stats[stat].n+1)
            if value > self._stats[stat].max:
                self._stats[stat].max = value
            if value < self._stats[stat].min:
                self._stats[stat].min = value
            self._stats[stat].n += 1
            
    def __getattr__(self, stat):
        with self.lock.readlock:
            return Bunch(self._stats[stat])
    
    def dump_all(self):
        with self.lock.readlock:
            return Bunch(self._stats)
    
    def _dump(self, stat):
        return ("[STATS-%s]: avg(%f) min(%f) max(%f) n(%d)" % (stat, self._stats[stat]['avg'], self._stats[stat]['min'], self._stats[stat]['max'], self._stats[stat]['n']))
    
    def dump(self, stat):
        with self.lock.readlock:
            return self._dump(stat)
    
    def dump_stats(self, log):
        with self.lock.readlock:
            for stat in self._stats:
                log.debug(self._dump(stat))

class Stats(StatsGatherer, Singleton):
    """
    Singleton version of StatsGatherer class
    
    """
    