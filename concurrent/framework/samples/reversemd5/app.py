# -*- coding: utf-8 -*-
"""
Sample application using Concurrent to perform a reverse hash

File: reversemd5.app.py
"""

from concurrent.framework.nodes.applicationnode import ApplicationNode
from concurrent.core.application.api import IApp
from concurrent.core.components.component import implements
from concurrent.core.async.task import Task
from concurrent.core.async.api import ITaskSystem
from concurrent.core.util.utils import is_digit

import time
import md5
import uuid
from uuid import UUID

class MD5HashReverseNode(ApplicationNode):
    """
    Reverse hash application
    """
    implements(IApp)
    
    def app_init(self):
        """
        Called just before the main entry. Used as the initialization point instead of the ctor
        """
        ApplicationNode.app_init(self)
    
    def app_main(self):
        """
        Applications main entry
        """
        return ApplicationNode.app_main(self)
    
    def get_task_system(self):
        """
        Called from the base class when we are connected to a MasterNode and we are 
        able to send computation tasks over
        """
        self.start_time = time.time()
        return MD5HashReverseTaskSystem(128)
    
    def work_finished(self, result, task_system):
        """
        Called when the work has been done, the results is what our ITaskSystem
        sent back to us. Check resukt for more info
        """
        print("Total time: {}".format(time.time() - self.start_time))
        if not result[1]:
            if result[0]:
                self.log.info("Hash as been reversed. Initial number was %s" % str(result[0]))
            else:
                self.log.info("Failed to reverse the hash :(")
        else:
            self.log.error("Computation failed: %s" % str(result[1]))
        self.shutdown_main_loop()
    
    def push_tasksystem_response(self, result):
        """
        We just added a ITaskSystem on the framwork. Check result for more info
        """
        self.log.info("Tasks system send to computation framework")

class MD5HashReverseTaskSystem(ITaskSystem):
    """
    The task system that is executed on the MasterNode and controls what jobs are required to be performed
    """
    
    def __init__(self, jobs=128, hash_number=1763965):
        """
        Default constructor used to initialize the base values. The ctor is
        executed on the ApplicationNode and not called on the MasterNode so we can 
        use it to initialize values.
        """
        super(MD5HashReverseTaskSystem, self).__init__()
        
        if not is_digit(hash_number):
            raise ValueError("hash_number must be a number!")
        
        self.start = 1
        self.end = 2000000
        self.target_hash = md5.new(str(hash_number)).hexdigest()
        
        # Create a number of jobs that will be processed
        self.jobs = jobs
        self.finished_jobs = 0
        
        self.step = (self.end - self.start) / jobs + 1
        self.result = None
    
    def init_system(self, master):
        """
        Initialize the system
        """
        pass
    
    def generate_tasks(self, master):
        """
        Generate the initial tasks this system requires
        """
        job_list = []
        for i in xrange(self.jobs):
            job_start = self.start + i*self.step
            job_end = min(self.start + (i + 1)*self.step, self.end)
            job_list.append(MD5ReverseTask("md5_reverse_task_{}".format(i), self.system_id, None, target_hash=self.target_hash, start=job_start, end = job_end))
        self.start_time = time.time()
        return job_list
        
    def task_finished(self, master, task, result, error):
        """
        Called once a task has been performed
        """
        self.finished_jobs += 1
        if result:
            self.result = result
    
    def gather_result(self, master):
        """
        Once the system stated that it has finsihed the MasterNode will request the required results that
        are to be send to the originator. Returns a tuple like (result, Error)
        """
        print("Calculated in {} seconds!".format(time.time() - self.start_time))
        return (self.result, None)
    
    def is_complete(self, master):
        """
        Ask the system if the computation has finsihed. If not we will go on and generate more tasks. This
        gets performed every time a tasks finishes.
        """
        # Wait until all computation has been finsihed or we have found the hash
        return self.result or self.finished_jobs == self.jobs

class MD5ReverseTask(Task):
    
    def __init__(self, name, system_id, client_id, **kwargs):
        Task.__init__(self, name, system_id, client_id)
        #print("Created task: %s" % str(self.task_id))
        
        self.target_hash = kwargs['target_hash']
        self.start = kwargs['start']
        self.end = kwargs['end']
        
    def __call__(self):
        """
        No try to find the hash
        """
        for i in xrange(self.start, self.end):
            if md5.new(str(i)).hexdigest() == self.target_hash:
                return i
        return None
    
    def finished(self, result, error):
        """
        Once the task is finished. Called on the MasterNode within the main thread once
        the node has recovered the result data.
        """
        #print("Task [{}] finished with: {}".format(self.name, result))
        pass
    
    def clean_up(self):
        """
        Called once a task has been performed and its results are about to be sent back. This is used
        to optimize our network and to cleanup the tasks input data
        """
        self.target_hash = None
        self.start = None
        self.end = None
