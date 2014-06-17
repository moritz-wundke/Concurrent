# -*- coding: utf-8 -*-
"""
Sample application demostrating the implementation of the mandlebrot fractal

File: mandlebrot.app.py
"""

from concurrent.framework.nodes.applicationnode import ApplicationNode
from concurrent.core.application.api import IApp
from concurrent.core.components.component import implements
from concurrent.core.async.task import Task
from concurrent.core.async.api import ITaskSystem
from concurrent.core.util.utils import is_digit, tprint
from concurrent.core.util.stats import time_push, time_pop


import numpy as np
from pylab import imshow, show
from timeit import default_timer as timer
from collections import defaultdict

import os

import time
import traceback

MAXLEN = 510  # maximum length of sequence

class MandlebrotNode(ApplicationNode):
    """
    DNA Curve Analysis application
    """
    implements(IApp)
    
    def app_init(self):
        """
        Called just before the main entry. Used as the initialization point instead of the ctor
        """
        super(MandlebrotNode, self).app_init()
    
    def app_main(self):
        """
        Applications main entry
        """
        return super(MandlebrotNode, self).app_main()
    
    def get_task_system(self):
        """
        Called from the base class when we are connected to a MasterNode and we are 
        able to send computation tasks over
        """
        self.start_time = time.time()
        self.image = np.zeros((1024, 1536), dtype = np.uint8)
        return MandlebrotTaskSystem(-2.0, 1.0, -1.0, 1.0, self.image, 20, 1)
    
    def work_finished(self, result, task_system):
        """
        Called when the work has been done, the results is what our ITaskSystem
        sent back to us. Check resukt for more info
        """
        print("Total time: {}".format(time.time() - self.start_time))
        # Reassamble result to be processed further
        try:
            task_system.do_post_run(result)
        except:
            traceback.print_exc()
        self.shutdown_main_loop()
    
    def push_tasksystem_response(self, result):
        """
        We just added a ITaskSystem on the framwork. Check result for more info
        """
        self.log.info("Tasks system send to computation framework")
    
    def push_tasksystem_failed(self, result):
        """
        We failed to push a ITaskSystem on the computation framework!
        """
        self.log.error("Tasks system failed to be send to framework!")
        # Check if the resuklt dict contains a traceback
        if "t" in result:
            self.log.error(result["t"])

class MandlebrotTaskSystem(ITaskSystem):
    """
    The task system that is executed on the MasterNode and controls what jobs are required to be performed
    """
    
    def __init__(self, min_x, max_x, min_y, max_y, image, iters, factor):
        """
        Default constructor used to initialize the base values. The ctor is
        executed on the ApplicationNode and not called on the MasterNode so we can 
        use it to initialize values.
        """
        super(MandlebrotTaskSystem, self).__init__()
        
        # Init task related stuff
        self.min_x = min_x
        self.max_x = max_x
        self.min_y = min_y
        self.max_y = max_y
        self.image = image
        self.iters = iters
        self.factor = factor
        
        self.height = self.image.shape[0]
        self.width = self.image.shape[1]        
        self.pixel_size_x = (self.max_x - self.min_x) / self.width
        self.pixel_size_y = (self.max_y - self.min_y) / self.height
        
    def do_post_run(self, result):
        """
        Once the computation finsihed we reassamble the image here
        """
        for x in range(self.width):
            for y in range(self.height):
                self.image[y, x] = result[x][y]
        
        imshow(self.image)
        show()
                
    def init_system(self, master):
        """
        Initialize the system
        """
        pass
    
    def generate_tasks(self, master):
        """
        Devide image in width part to distribute work
        """
        
        # Create a number of jobs that will be processed
        self.jobs = 0
        self.finished_jobs = 0
        self.result_dict = {}
        
        job_list = []
        workload = []
        
        rows = 0
        x = 0

        for x in range(self.width):
            # Distribute using rows
            rows += 1
            
            real = self.min_x + x * self.pixel_size_x
            for y in range(self.height):
                imag = self.min_y + y * self.pixel_size_y
                workload.append((x, y, real, imag, self.iters))
            
            # every self.factor rows create a task with the workload
            if rows == self.factor:
                job_list.append(MandlebrotTask("mandle_{}".format(x), self.system_id, iters = self.iters, workload = workload))
                workload = []
                rows = 0
        
        # Add last task with rest of workload
        if len(workload) > 0:
            job_list.append(MandlebrotTask("mandle_{}".format(x), self.system_id, workload = workload))
            
        self.jobs = len(job_list)
        self.start_time = time.time()
        return job_list
        
    def task_finished(self, master, task, result, error):
        """
        Called once a task has been performed
        """
        self.finished_jobs += 1
        if result:
            self.result_dict.update(result)
    
    def gather_result(self, master):
        """
        Once the system stated that it has finsihed the MasterNode will request the required results that
        are to be send to the originator. Returns a tuple like (result, Error)
        """
        print("Calculated in {} seconds!".format(time.time() - self.start_time))
        return self.result_dict
    
    def is_complete(self, master):
        """
        Ask the system if the computation has finsihed. If not we will go on and generate more tasks. This
        gets performed every time a tasks finishes.
        """
        #print("%d -> %d" % (self.finished_jobs,self.jobs))
        # Wait for all tasks to finish
        return self.finished_jobs == self.jobs

def do_mandel(x, y, max_iters):
    """
        Given the real and imaginary parts of a complex number,
        determine if it is a candidate for membership in the Mandelbrot
        set given a fixed number of iterations.
    """
    c = complex(x, y)
    z = 0.0j
    for i in range(max_iters):
        z = z*z + c
        if (z.real*z.real + z.imag*z.imag) >= 4:
            return i

    return max_iters

def dd():
    return defaultdict(int)
    
class MandlebrotTask(Task):
    
    def __init__(self, name, system_id, **kwargs):
        Task.__init__(self, name, system_id, **kwargs)
        self.workload = kwargs['workload']
        self.iters = kwargs['iters']
    
    def _dd(self):
        return defaultdict(int)
        
    def __call__(self):
        """
        No try to find the hash
        """
        result = defaultdict(dd)
        for work in self.workload:
            result[work[0]][work[1]] = do_mandel(work[2], work[3], self.iters)
        return result
    
    def finished(self, result, error):
        """
        Once the task is finished. Called on the MasterNode within the main thread once
        the node has recovered the result data.
        """
        pass
