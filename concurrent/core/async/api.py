# -*- coding: utf-8 -*-
"""
Base interface for async tasks classes
"""
from concurrent.core.components.component import Interface

import uuid

__all__ = ['ITaskManager', 'ITaskSystem', 'ITaskScheduler', 'ITaskScheduleStrategy']

class ITaskManager(Interface):
    """
    Interface used to define what a task manager is for us
    """

    def init():
        """
        Initialize the manager
        """
    
    def get_num_workers():
        """
        Return the number of workers we use for our processing
        """
        
    def start():
        """
        Start our worker processes
        """

    def stop():
        """
        Stop our worker processes
        """

    def update_pool(_num_workers):
        """
        Set the number of workers the task manager should use
        """

    def push_task(task):
        """
        Push a task that should be completed by the workers
        """

    def wait_for_all():
        """
        Wait until all tasks has been finished
        """
    
    def get_results_queue():
        """
        Return a refernce to the result queue
        """
    
    def create_task(task_class):
        """
        Create a task using a given type. TaskManager will assign a unique id to the created task
        """
        
    def task_finished(task, result, error):
        """
        Called once a task has been performed
        """

# TODO: If a TaskSystem finishes how can be delete remaining tasks if any? How can they be poisoned?

class ITaskSystem(object):
    """
    A task system is an implemented system that provides a scheduler with tasks to be executed
    """
    def __init__(self):
        """
        Default constructor used to initialize the base values. The ctor is
        executed on the ApplicationNode and not called on the MasterNode so we can 
        use it to initialize values.
        """
        # Create a number of jobs that will be processed
        self._system_id = uuid.uuid1()
    
    @property
    def system_id(self):
        return self._system_id
    
    def init_system(self, master):
        """
        Initialize the system
        """
        raise NotImplementedError("init_system(self, master) not implemented!")
    
    def get_system_id(self):
        raise NotImplementedError("get_system_id(self) not implemented!")
    
    def generate_tasks(self, master):
        """
        Generate the initial tasks this system requires
        """
        raise NotImplementedError("generate_tasks(self, master) not implemented!")
    
    def task_finished(self, master, task, result, error):
        """
        Called once a task has been performed
        """
        raise NotImplementedError("task_finished(self, master, task, result, error) not implemented!")
    
    def gather_result(self, master):
        """
        Once the system stated that it has finsihed the MasterNode will request the required results that
        are to be send to the originator. Returns a tuple like (result, Error)
        """
        raise NotImplementedError("gather_result(self, master) not implemented!")
    
    def is_complete(self, master):
        """
        Ask the system if the computation has finsihed. If not we will go on and generate more tasks
        """
        raise NotImplementedError("is_complete(self, master) not implemented!")
    
class ITaskScheduleStrategy(Interface):
    """
    Implements a schedule strategy to select the next valid slave that should process a given task
    """
    
    def setup(scheduler, master):
        """
        Setup the stratey with required data
        """
    
    def rate(slave):
        """
        Rate a slave without
        """
    
    def get_next_slave():
        """
        Get the slave that should process the next task
        """

class ITaskScheduler(Interface):
    """
    Interface used by our distributed task scheduler. A scheduler receives an implemented system
    that will be executed on the distributed system through pickleing Python instances.
    """
    
    def setup(master):
        """
        Setup the scheduler with required data
        """
        
    def rate_slaves():
        """
        Update slaves
        """
            
    def start_system(task_system):
        """
        Start an incomming task system
        """
    
    def push_tasks(tasks):
        """
        Push all tasks on the global task queue
        """
    
    def push_task(task):
        """
        Put a task on the global task queue
        """
    
    def handle_task(task):
        """
        Send a task to a slave or in case it failed queue the task back
        """
        
    def _tasked_pushed(slave_id):
        """
        A slave has aquired a new task, update its rank
        """
    
    def task_finished(task, result, error):
        """
        A slave has finished a new task, update its rank
        """
