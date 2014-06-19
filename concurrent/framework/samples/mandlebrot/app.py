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
from concurrent.core.config.config import BoolItem

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
    Application node distributing the computation of the mandlebrot set using an autonomous task system
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
        self.system = MandlebrotTaskSystem(-2.0, 1.0, -1.0, 1.0, self.image, 20, 1)
        return self.system
    
    def work_finished(self, result, task_system):
        """
        Called when the work has been done, the results is what our ITaskSystem
        sent back to us. Check resukt for more info
        """
        print("Total time: {}".format(time.time() - self.start_time))
        self.shutdown_main_loop()
        # Reassamble result to be processed further
        try:
            self.system.do_post_run(result)
        except:
            traceback.print_exc()
    
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

class MandlebrotSimpleNode(ApplicationNode):
    """
    Application node distributing the computation of the mandlebrot set using just tasks
    """
    implements(IApp)
    
    send_task_batch = BoolItem('mandlebrotsample', 'task_batch', True,
        """Should we send all tasks one by one or should we batch them into a hughe list""")
    
    def app_init(self):
        """
        Called just before the main entry. Used as the initialization point instead of the ctor
        """
        super(MandlebrotSimpleNode, self).app_init()
    
    def app_main(self):
        """
        Applications main entry
        """
        return super(MandlebrotSimpleNode, self).app_main()
    
    def get_task_system(self):
        """
        Called from the base class when we are connected to a MasterNode and we are 
        able to send computation tasks over
        """
        # Do not create a tasks system, we will handle tasks on our own
        return None
    
    def start_processing(self):
        """
        Called when the app is not using a ITaskSystem and will instead just add tasks and
        will take care of the task flow itself
        """
        self.log.info("Starting computation")
        if self.send_task_batch:
            self.log.info(" Task batching enabled")

        self.image = np.zeros((1024, 1536), dtype = np.uint8)
        
        # Init task related stuff
        self.min_x = -2.0
        self.max_x =  1.0
        self.min_y = -1.0
        self.max_y = 1.0
        self.iters = 20
        self.factor = 1
        
        self.height = self.image.shape[0]
        self.width = self.image.shape[1]        
        self.pixel_size_x = (self.max_x - self.min_x) / self.width
        self.pixel_size_y = (self.max_y - self.min_y) / self.height
        
        # Job handling (very optimistic :D)
        self.jobs = 0
        self.finished_jobs = 0
        
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
            
            # every self.factor rows create a task with the workload. Note that in this case we will force the system_id to be None while setting the client id
            if rows == self.factor:
                if self.send_task_batch:
                    job_list.append(MandlebrotTask("mandle_{}".format(x), None, self.node_id_str, iters = self.iters, workload = workload))
                else:
                    self.push_task(MandlebrotTask("mandle_{}".format(x), None, self.node_id_str, iters = self.iters, workload = workload))
                    self.jobs += 1
                workload = []
                rows = 0
                
        # Add last task with rest of workload
        if len(workload) > 0:
            if self.send_task_batch:
                job_list.append(MandlebrotTask("mandle_{}".format(x), None, self.node_id_str, workload = workload))
            else:
                self.push_task(MandlebrotTask("mandle_{}".format(x), None, self.node_id_str, workload = workload))
                self.jobs += 1
        
        if self.send_task_batch:
            self.jobs = len(job_list)
        self.start_time = time.time()
        
        # Send batch or check for eventual end condition
        if self.send_task_batch:
            self.push_tasks(job_list)
        else:
            # Check in case we are already done!
            self.check_finished()
    
    def task_finished(self, task, result, error):
        """
        Called when a task has been done
        """        
        # Integrate results in our image
        if result:
            for x, column in result.iteritems():
                for y, value in column.iteritems():
                    self.image[y, x] = value
        
        self.finished_jobs += 1  
        self.check_finished()
    
    def check_finished(self):
        """
        Check if we finsihed all computation or not
        """
        if self.finished_jobs == self.jobs:
            self.log.info("All tasks finished!!")
            print("Calculated in {} seconds!".format(time.time() - self.start_time))
            self.shutdown_main_loop()
            imshow(self.image)
            show()
    
    def push_task_response(self, result):
        """
        We just add a Task to the computation framework
        """
        pass
        #self.log.info("Task send to computation framework")
    
    def push_task_failed(self, result):
        """
        We failed to add a Task to the computation framework
        """
        self.log.info("Failed to send task send to computation framework")
    
    def push_tasks_response(self, result):
        """
        We just add a set of Tasks to the computation framework
        """
        self.log.info("Tasks send to computation framework")
    
    def push_tasks_failed(self, result):
        """
        We failed to add a set of Tasks to the computation framework
        """
        self.log.info("Failed to send tasks send to computation framework")
    
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
                job_list.append(MandlebrotTask("mandle_{}".format(x), self.system_id, None, iters = self.iters, workload = workload))
                workload = []
                rows = 0
        
        # Add last task with rest of workload
        if len(workload) > 0:
            job_list.append(MandlebrotTask("mandle_{}".format(x), self.system_id, None, workload = workload))
            
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

class MandlebrotTask(Task):
    
    def __init__(self, name, system_id, client_id, **kwargs):
        Task.__init__(self, name, system_id, client_id)
        self.workload = kwargs['workload']
        self.iters = kwargs['iters']
        
    def __call__(self):
        """
        Calculate assigned work
        """
        result = {}
        for work in self.workload:
            if not work[0] in result:
                result[work[0]] = {}
            result[work[0]][work[1]] = do_mandel(work[2], work[3], self.iters)
        return result
    
    def finished(self, result, error):
        """
        Once the task is finished. Called on the MasterNode within the main thread once
        the node has recovered the result data.
        """
        pass
    
    def clean_up(self):
        """
        Called once a task has been performed and its results are about to be sent back. This is used
        to optimize our network and to cleanup the tasks input data
        """
        self.workload = None
        self.iters = None