# -*- coding: utf-8 -*-
"""
Sample application which just does a set of expensive tasks on the system to demostrate its viability

File: expensive.app.py
"""

from concurrent.framework.nodes.applicationnode import ApplicationNode
from concurrent.core.application.api import IApp
from concurrent.core.components.component import implements
from concurrent.core.async.task import Task
from concurrent.core.async.api import ITaskSystem
from concurrent.core.config.config import BoolItem, IntItem

import os

import time
import traceback

class ExpensiveNode(ApplicationNode):
    """
    Application node distributing the computation of an expensive task
    """
    implements(IApp)
    
    time_per_task = IntItem('expensivesample', 'time_per_task', 1,
        """Time each task will perform on doing nothind (active wait) to simulate an expensive computation""")
    
    num_tasks = IntItem('expensivesample', 'num_tasks', 8,
        """Number of tasks that must be performend""")
    
    def app_init(self):
        """
        Called just before the main entry. Used as the initialization point instead of the ctor
        """
        super(ExpensiveNode, self).app_init()
    
    def app_main(self):
        """
        Applications main entry
        """
        return super(ExpensiveNode, self).app_main()
    
    def get_task_system(self):
        """
        Called from the base class when we are connected to a MasterNode and we are 
        able to send computation tasks over
        """
        self.start_time = time.time()
        self.system = ExpensiveNodeTaskSystem(self.time_per_task, self.num_tasks)
        return self.system
    
    def work_finished(self, result, task_system):
        """
        Called when the work has been done, the results is what our ITaskSystem
        sent back to us. Check resukt for more info
        """
        end_time = time.time() - self.start_time
        self.log.info("Total time: {}".format(end_time))
        
        # Print expected single threaded time and improvement
        expected_time = self.time_per_task * self.num_tasks
        self.log.info("Plain python expected time: {}".format(expected_time))
        self.log.info("Concurrent improvememnet: {}%".format((expected_time/end_time)*100.0))
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

class ExpensiveSimpleNode(ApplicationNode):
    """
    Application node distributing the computation of the mandlebrot set using just tasks
    """
    implements(IApp)
    
    send_task_batch = BoolItem('expensivesample', 'task_batch', True,
        """Should we send all tasks one by one or should we batch them into a hughe list""")
    
    time_per_task = IntItem('expensivesample', 'time_per_task', 1,
        """Time each task will perform on doing nothind (active wait) to simulate an expensive computation""")
    
    num_tasks = IntItem('expensivesample', 'num_tasks', 8,
        """Number of tasks that must be performend""")
    
    def app_init(self):
        """
        Called just before the main entry. Used as the initialization point instead of the ctor
        """
        super(ExpensiveSimpleNode, self).app_init()
    
    def app_main(self):
        """
        Applications main entry
        """
        return super(ExpensiveSimpleNode, self).app_main()
    
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
            
        self.start_time = time.time()
        self.finished_jobs = 0
        if self.send_task_batch:
            self.push_tasks( [ExpensiveTask("expensive_{}".format(i), None, self.node_id_str, sleep_time=self.time_per_task) for i in range(self.num_tasks)])
        else:
            for i in range(self.num_tasks):
                self.push_task( ExpensiveTask("expensive_{}".format(i), None, self.node_id_str, sleep_time=self.time_per_task) )
            self.check_finished()
    
    def task_finished(self, task, result, error):
        """
        Called when a task has been done
        """        
        self.finished_jobs += 1  
        self.check_finished()
    
    def check_finished(self):
        """
        Check if we finsihed all computation or not
        """
        self.log.info("%d -> %d" % (self.finished_jobs,self.num_tasks))
        if self.finished_jobs == self.num_tasks:
            self.log.info("All tasks finished!!")
            end_time = time.time() - self.start_time
            self.log.info("Total time: {}".format(end_time))
            
            # Print expected single threaded time and improvement
            expected_time = self.time_per_task * self.num_tasks
            self.log.info("Plain python expected time: {}".format(expected_time))
            self.log.info("Concurrent improvememnet: {}%".format((expected_time/end_time)*100.0))
            self.shutdown_main_loop()
            
    
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
    
class ExpensiveNodeTaskSystem(ITaskSystem):
    """
    The task system that is executed on the MasterNode and controls what jobs are required to be performed
    """
    
    def __init__(self, time_per_task, num_tasks):
        """
        Default constructor used to initialize the base values. The ctor is
        executed on the ApplicationNode and not called on the MasterNode so we can 
        use it to initialize values.
        """
        super(ExpensiveNodeTaskSystem, self).__init__()
        
        # Init task related stuff
        self.time_per_task = time_per_task
        self.num_tasks = num_tasks
                
    def init_system(self, master):
        """
        Initialize the system
        """
        pass
    
    def generate_tasks(self, master):
        """
        Create task set
        """
        self.start_time = time.time()
        self.finished_jobs = 0
        return [ExpensiveTask("expensive_{}".format(i), self.system_id, None, sleep_time=self.time_per_task) for i in range(self.num_tasks)]
        
    def task_finished(self, master, task, result, error):
        """
        Called once a task has been performed
        """
        self.finished_jobs += 1
    
    def gather_result(self, master):
        """
        Once the system stated that it has finsihed the MasterNode will request the required results that
        are to be send to the originator. Returns the total time spend on the master.
        """
        total_time = time.time() - self.start_time
        self.log.info("Calculated in {} seconds!".format(total_time))
        return total_time
    
    def is_complete(self, master):
        """
        Ask the system if the computation has finsihed. If not we will go on and generate more tasks. This
        gets performed every time a tasks finishes.
        """
        self.log.info("%d -> %d" % (self.finished_jobs,self.num_tasks))
        # Wait for all tasks to finish
        return self.finished_jobs == self.num_tasks

class ExpensiveTask(Task):
    
    def __init__(self, name, system_id, client_id, **kwargs):
        Task.__init__(self, name, system_id, client_id)
        self.sleep_time = kwargs['sleep_time']
        
    def __call__(self):
        """
        Calculate assigned work
        """
        # Simulate an active wait, this is more accurate then sleeping
        end_time = time.time() + self.sleep_time
        while True:
            if time.time() > end_time:
                break
        return self.sleep_time
    
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
        pass