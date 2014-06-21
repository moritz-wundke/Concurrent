# -*- coding: utf-8 -*-
"""
Base class for any of our async tasks that a job is made of.
"""
from threading import Thread
from inspect import Traceback
__all__ = ['Task', 'GenericTaskManager', 'GenericTaskSchduler']

from concurrent.core.components.component import Component, implements
from concurrent.core.async.api import ITaskManager, ITaskScheduler, ITaskScheduleStrategy
from concurrent.core.async.threads import InterruptibleThread
from concurrent.core.config.config import IntItem, ExtensionPointItem, HostItem
from concurrent.core.application.api import NodeType, NodeState
from concurrent.core.util.stats import Stats
from concurrent.core.util.utils import tprint
from concurrent.core.transport.tcpsocket import send_to_zmq_zipped, receive_from_zmq_zipped, TCPSocketZMQ

from bunch import Bunch
from collections import OrderedDict

import traceback
import urllib2
import multiprocessing
import threading
import zmq
import os
import time
import uuid
import sys

# Port used for our worker process using zmq instead of queues for best performance
WORKER_PORT = 5557

# http://glitterbug.in/blog/task-queuing-in-django-with-zeromq-5/show/
# http://zguide.zeromq.org/py:rtreq
# http://www.jeffknupp.com/blog/2014/02/11/a-celerylike-python-task-queue-in-55-lines-of-code/
# Or back to queues?

# We use zipped pickles because they transmit way faster!

class Task(object):
    """
    A simple tasks that just executes a function in a fire and forget way
    """
    def __init__(self, name, system_id, client_id):
        """
        Initialize the task itself
        """
        self._name = name
        self._id = str(uuid.uuid1())
        
        # The system ID is the ID of the system that owns the task. We use this
        # ID to send the task back to its owner once finished
        self._system_id = system_id
        
        # The slave ID is the ID of the slave that processed the task
        self.slave_id = None
        
        # The client ID is set when a push a task onto the framework
        self.client_id = client_id
            
    @property
    def name(self):
        return self._name
    
    @property
    def task_id(self):
        return self._id
    
    @property
    def system_id(self):
        return self._system_id

    def __call__(self):
        """
        Executer a task
        """
        raise NotImplementedError("Subclasses should implement this!")
    
    def clean_up(self):
        """
        Called once a task has been performed and its results are about to be sent back. This is used
        to optimize our network and to cleanup the tasks input data
        """
        pass
    
    def finished(self, result, error):
        """
        Once the task is finished. Called on the MasterNode within the main thread once
        the node has recovered the result data.
        """
        raise NotImplementedError("Subclasses should implement this!")

class TaskProcess(multiprocessing.Process):
    """
    A TaskProcess is the base consumer class of work orders
    """

    def __init__(self, result_queue, process_id, task_queue, identity, host, port):
        multiprocessing.Process.__init__(self)
        self._id = process_id
        self._pid = 0
        self.result_queue = result_queue
        self.task_queue = task_queue
        self.identity = identity
        self.host = host
        self.port = port
        
        # Create logger for each process!
    
    def log(self, msg):
        tprint("[%s][%d] %s" % (self.__class__.__name__, self._pid, msg))

    def run(self):
        self._pid = os.getpid()
        #self.context = zmq.Context()
        #self.work_receiver = context.socket(zmq.PULL)
        #self.work_receiver.connect("tcp://127.0.0.1:%d" % WORKER_PORT)
        
        # Create sockets to communicate with master, this way we optimize our resources
        self.socket=TCPSocketZMQ("{}_{}".format(self._id, self.identity), self.host, self.port)
        self.socket.connect()
        
        self.stats = Stats.getInstance()
        self.log("Running")
        while True:
            try:
                #next_task = receive_from_zmq_zipped(self.work_receiver)
                next_task = self.task_queue.get()
                if next_task is None:
                    # A None task is used to shut us down
                    self.task_queue.task_done()
                    break
                result = None
                try:
                    start = time.time()
                    result = next_task()
                    self.task_queue.task_done()
                    ellapsed = time.time() - start
                    error = None
                    self.stats.add_avg("task-time",ellapsed)
                    #self.log("Finished [%s:%s]" % (next_task.name, next_task.task_id))
                except Exception as err:
                    result = None
                    error = err
                finally:
                    #self.result_queue.put(Bunch({'task':next_task,'result':result,'error':error}))
                    #print("sending back")
                    next_task.clean_up()
                    self.socket.send_to('task_finished', next_task, result, error)
            except KeyboardInterrupt:
                self.log("Keyboard interrupt received, exiting!")
                break
        self.socket.close()
        #self.work_receiver.close()
        #self.context.term()
        self.log("Exiting")

class GenericTaskManager(Component):
    implements(ITaskManager)
    """
    Simple task manager used in simple single job applications
    """
    
    num_workers = IntItem('GenericTaskManager', 'num_workers', -1,
        """Number of worker processed to be created, -1 will spawn as much as physical cores.""")
    
    def __init__(self, *args, **kwargs):
        Component.__init__(self, *args, **kwargs)
        # Initialize base manager stuff
        self._num_workers = 0
        self.results = multiprocessing.JoinableQueue()
        
    def init(self, identity, address):
        """
        Initialize the manager
        """
        self.identity = identity
        self.host = address[0]
        self.port = address[1]
        
        self._num_workers = self.num_workers
        if self._num_workers <= 0:
            self._num_workers = multiprocessing.cpu_count()
            
        # We now prepare our queues, both the joinable and the results
        # queues. Then we just create a process for each worker
        self.tasks = multiprocessing.JoinableQueue()
        self.processes = [TaskProcess(self.results, i, self.tasks, self.identity, self.host, self.port) for i in range(self._num_workers)]
        #self.processes = [TaskProcess(self.results, i) for i in range(self._num_workers)]
        
        context = zmq.Context()
        self.ventilator_send = context.socket(zmq.PUSH)
        self.ventilator_send.bind("tcp://127.0.0.1:%d" % WORKER_PORT)
    
    def get_num_workers(self):
        """
        Return the number of workers we use for our processing
        """
        return self._num_workers
    
    def start(self):
        """
        Start our worker processes
        """
        for worker in self.processes:
            worker.daemon = True
            worker.start()

    def stop(self):
        """
        Stop our worker processes
        """
        for i in xrange(self._num_workers):
            #send_to_zmq_zipped(self.ventilator_send, None)
            self.tasks.put(None)
        # Poison for result listener
        self.results.put(None)

    def update_pool(self, _num_workers=-1):
        """
        Set the number of workers the task manager should use
        """
        self.stop()
        self.init(_num_workers)
        self.start()

    def push_task(self, task):
        """
        Push a task that should be completed by the workers
        """
        try:
            #send_to_zmq_zipped(self.ventilator_send, task)
            self.tasks.put(task)
        except:
            traceback.print_exc()
        return True

    def wait_for_all(self):
        """
        Wait until all tasks has been finished
        """
        pass
    
    def get_results_queue(self):
        """
        Return a refernce to the result queue
        """
        return self.results
    
    def task_finished(self, task, result, error):
        """
        Called once a task has been performed
        """
        task.finished(result, error)

class GenericTaskScheduleStrategy(Component):
    implements(ITaskScheduleStrategy)
    """
    Implements a schedule strategy to select the next valid slave that should process a given task.
    We update the workers and rank them so that we give a slave with idle workers a better
    rating than a worker with pending work.
     - If rank > 0 => Slave has idle processes
     - If rank == 0 => Slave has currently the same number of tasks then processes
     - If rank < 0 => Slave has currently more tasks thank workers
    """
        
    def setup(self, scheduler, master):
        self.scheduler = scheduler
        self.master = master
    
    def rate(self, slave):
        """
        Rate a slave without any lock. Less if better.
        """
        # Worst rating if we have a slave without workers!
        if slave.workers < 1:
            return sys.float_info.max
        
        # Basic rating is the task/worker ratio
        rating = max(0, slave.tasks / (slave.workers * 1.0))
        
        # TODO: Add task finished per second ratio
        
        return rating
    
    def get_next_slave(self):
        """
        Get the slave that should process the next task, get the one with better rating
        """
        if self.master.node_registry:
            # Find the best score
            best_rating = sys.float_info.max
            best_node = None
            for node in self.master.node_registry:
                if self.master.node_registry[node] and self.master.node_registry[node].state == NodeState.active \
                        and self.master.node_registry[node].type == NodeType.slave \
                        and self.master.node_registry[node].rating < best_rating:
                    best_rating = self.master.node_registry[node].rating
                    best_node = node
            
            # Get all nodes with the same or similar score (some nice epsilon?)
            #Nodes ...
            #for node in self.master.node_registry:
            #    if node and node.rating == best_rating:
            #        best_rating = node.rating            
            # Get a random slave form the first 10% of slaves. This will give us a bit
            # of randomness in case sending the tasks failes
            
            # For now we just use the best node
            if best_node:
                return best_node
        return None

class schedule_thread(InterruptibleThread):
    """
    The schedule thread is responsible to pickup tasks from the global task queue and to send then to a slave.
    """
    def __init__(self, log, task_queue, callback):
        InterruptibleThread.__init__(self, log)
        self.task_queue = task_queue
        self.callback = callback
        
    def run(self):
        while True:
            task = self.task_queue.get()
            if task is None:
                # A None task is used to shut us down
                self.task_queue.task_done()
                break
            self.task_queue.task_done()
            # Send task to one of our slaves
            self.callback(task)
        self.log.info("schedule_thread exiting")
    
    def stop(self):
        try:
            self.task_queue.put(None)
            self.join()
        except:
            pass
        self.log.info("schedule_thread stopped")
        
class GenericTaskScheduler(Component):
    implements(ITaskScheduler)
    """
    Interface used by our distributed task scheduler. A scheduler receives an implemented system
    that will be executed on the distributed system through pickleing Python instances.
    """
    
    strategy = ExtensionPointItem('generictaskscheduler', 'strategy', ITaskScheduleStrategy, 'GenericTaskScheduleStrategy',
        """Task schedulers used to schedule execution""")
    
    def __init__(self):
        Component.__init__(self)
        self.stats = Stats.getInstance()
        
        # Map that maps tasks and slaves to be able to resend the tasks if the slave was deleted from the system
        self.task_map = {}
        
    def setup(self, master):
        self.master = master
        self.lock = self.master.registry_lock
        
        # This is the global systems task queue. Every time we add tasks we will add them to this queue.
        # The global queue is where the current strategy will pickup tasks and decide which ones shall
        # be sent over a slave to be processed (this is getting done from a thread that waits for the queue)
        # If a new tasks gets added or a task gets completed we will notify the strategy which then decides to 
        # pickup and process a new task.
        self.tasks = multiprocessing.JoinableQueue()
        
        # Schedule thread which will pickup processabel task and send them to a good slave
        self.schedule_thread = schedule_thread(self.log, self.tasks, self.handle_task)
        self.schedule_thread.start()
        
        # Do not pass the lock to the strategy, we have to ensure we handle locks for it
        self.strategy.setup(self, self.master)
    
    def stop(self):
        self.schedule_thread.stop()
        
    def _valid_id_no_lock(self, slave_id):
        """
        Check if slave id is pointing to a valid slave without any lock
        """
        return slave_id in self.master.node_registry and self._valid_slave_no_lock(self.master.node_registry[slave_id])
    
    def _valid_slave_no_lock(self, slave):
        """
        Check if a slave is valid without using any locks
        """
        return slave and slave.type == NodeType.slave and slave.state == NodeState.active
        
    def rate_slaves(self):
        """
        Update slaves
        """
        with self.lock.writelock:
            start = time.time()
            for slave_id in self.master.node_registry:
                if self._valid_slave_no_lock(self.master.node_registry[slave_id]):
                    self.master.node_registry[slave_id].rating = self.strategy.rate(self.master.node_registry[slave_id])
            ellapsed = time.time() - start
            self.stats.add_avg("GenericTaskScheduleStrategy-rate-time",ellapsed)
            
    def start_system(self, task_system):
        """
        Start an incomming task system
        """
        self.push_tasks(task_system.generate_tasks(self.master))
    
    def push_tasks(self, tasks):
        """
        Push all tasks on the global task queue
        """
        for task in tasks:
            self.push_task(task)
    
    def push_task(self, task):
        """
        Put a task on the global task queue
        """
        # Do not poison ourselfs!
        if task:
            self.tasks.put(task)
    
    def handle_task(self, task):
        """
        Send a task to a slave or in case it failed queue the task back
        """
        with self.lock.readlock:
            reschedule = True
            try:
                slave_id = self.strategy.get_next_slave()
                if slave_id:
                    #TODO: Pickle task and send to slave
                    task.slave_id = slave_id
                    start = time.time()
                    self.master.node_registry[task.slave_id].tcp_proxy.push_task(task)
                    #print("Sending task: {} in {}".format(task.name, time.time() - start))
                    reschedule = False
                    # Add task id to this slave so we could resend the task
                    self._tasked_pushed(task.slave_id)       
            except Exception as e:
                #self.log.error("Failed to send task to slave: %s. Queueing task again!" % str(e))
                self.stats.add_avg("GenericTaskScheduler-task-send-failed")
                
            # Make sure we try it again!
            if reschedule:
                self.push_task(task)
        
    def _tasked_pushed(self, slave_id):
        """
        A slave has aquired a new task, update its rank
        """
        #with self.lock.readlock:
        if self._valid_id_no_lock(slave_id):
            self.master.node_registry[slave_id].tasks += 1
            self.master.node_registry[slave_id].rating = self.strategy.rate(self.master.node_registry[slave_id])
            #print("Push: {}".format(self.master.node_registry[slave_id].tasks))
    
    def task_finished(self, task, result, error):
        """
        A slave has finished a new task, update its rank
        """
        task.finished(result, error)
        # Do not aquiere any write lock if the id is not valid!
        #with self.lock.readlock:
        if self._valid_id_no_lock(task.slave_id):
            self.master.node_registry[task.slave_id].tasks -= 1
            self.master.node_registry[task.slave_id].rating = self.strategy.rate(self.master.node_registry[task.slave_id])
            #print("Pop: {}".format(self.master.node_registry[task.slave_id].tasks))
        
        #self.strategy.task_finished(result['task_id'] check results!)

class ZMQTaskManager(Component, threading.Thread):
    implements(ITaskManager)
    """
    Simple task manager used in simple single job applications
    """
    
    num_workers = IntItem('ZMQTaskManager', 'num_workers', -1,
        """Number of worker processed to be created, -1 will spawn as much as physical cores.""")
    
    master_backend_port = HostItem('ZMQTaskManager', 'master_backend_port', 'localhost:5001',
        """Masters backend port where we will request tasks.""")
    
    def __init__(self):
        threading.Thread.__init__(self)
        Component.__init__(self)
        
        # Some thread related stuff
        self.daemon = True
        self.kill_switch = False
        
        # Create contect and socket
        self.context = zmq.Context()
        
        # Initialize base manager stuff
        self._num_workers = 0
        self.results = multiprocessing.JoinableQueue()
        
    def init(self, identity, address):
        """
        Initialize the manager
        """
        self.identity = identity
        self.host = address[0]
        self.port = address[1]
        
        self._num_workers = self.num_workers
        if self._num_workers <= 0:
            self._num_workers = multiprocessing.cpu_count()
            
        # We now prepare our queues, both the joinable and the results
        # queues. Then we just create a process for each worker
        self.tasks = multiprocessing.JoinableQueue()
        self.processes = [TaskProcess(self.results, i, self.tasks, self.identity, self.host, self.port) for i in range(self._num_workers)]
        #self.processes = [TaskProcess(self.results, i) for i in range(self._num_workers)]
        
        context = zmq.Context()
        self.ventilator_send = context.socket(zmq.PUSH)
        self.ventilator_send.bind("tcp://127.0.0.1:%d" % WORKER_PORT)
    
    def get_num_workers(self):
        """
        Return the number of workers we use for our processing
        """
        return self._num_workers
    
    def start(self):
        """
        Start our worker processes
        """
        threading.Thread.start(self)
        for worker in self.processes:
            worker.daemon = True
            worker.start()

    def stop(self):
        """
        Stop our worker processes
        """
        self.log.info("Shutting down ZMQTaskManager")
        for i in xrange(self._num_workers):
            #send_to_zmq_zipped(self.ventilator_send, None)
            self.tasks.put(None)
        # Poison for result listener
        self.results.put(None)
        
        # Kill our own thread
        self.kill_switch = True
        self.context.term()
        self.join(5000)
        self.log.info("ZMQTaskManager shutdown finished")
        
    def run(self):
        self.log.info("ZMQTaskManager started")
        
        # Create and connect to our scheduler socket
        self.socket = self.context.socket(zmq.PULL)
        self.socket.connect('tcp://{host}:{port}'.format(host=self.master_backend_port[0], port=self.master_backend_port[1]))
        
        # Start receiving messages
        while not self.kill_switch:
            try:
                next_task = receive_from_zmq_zipped(self.socket)
                #tprint("Receiving task")
                self.push_task(next_task)
            except zmq.ContextTerminated:
                break
            except zmq.ZMQError as e:
                if e.errno == zmq.EAGAIN:
                    pass  # no message was ready
                else:
                    break
            except:
                traceback.print_exc()
            
        self.socket.close()
        self.log.info("ZMQTaskManager stopped")

    def update_pool(self, _num_workers=-1):
        """
        Set the number of workers the task manager should use
        """
        self.stop()
        self.init(_num_workers)
        self.start()

    def push_task(self, task):
        """
        Push a task that should be completed by the workers
        """
        try:
            #send_to_zmq_zipped(self.ventilator_send, task)
            self.tasks.put(task)
        except:
            traceback.print_exc()
        return True

    def wait_for_all(self):
        """
        Wait until all tasks has been finished
        """
        pass
    
    def get_results_queue(self):
        """
        Return a refernce to the result queue
        """
        return self.results
    
    def task_finished(self, task, result, error):
        """
        Called once a task has been performed
        """
        task.finished(result, error)
        
class ZMQTaskScheduler(Component, threading.Thread):
    implements(ITaskScheduler)
    """
    Different task scheduler implementation using ZMQ push/pull sockets. Uses a simple round-robin
    mechanism to handle multiple slaves.
    """
    
    frontend_port = IntItem('ZMQTaskScheduler', 'frontend_port', 5000,
        """Frontend port used to send tasks to the scheduler""")
    
    backend_port = IntItem('ZMQTaskScheduler', 'backend_port', 5001,
        """Backend port used to send tasks to the scheduler. Slaves will receive tasks on it.""")
    
    def __init__(self):
        threading.Thread.__init__ (self)
        Component.__init__(self)
        self.stats = Stats.getInstance()
        
        # Some thread related stuff
        self.daemon = True
        self.kill_switch = False
        
        # The socket framework
        self.context = zmq.Context()
        self.frontend = self.context.socket(zmq.PULL)
        self.frontend.bind('tcp://*:{port}'.format(port=self.frontend_port))
        self.backend = self.context.socket(zmq.PUSH)
        self.backend.bind('tcp://*:{port}'.format(port=self.backend_port))
        
        # Connected socket locally to frontend to send tasks, this socket
        # provides a lock to be able to be thread-safe
        self.frontend_push = self.context.socket(zmq.PUSH)
        self.frontend_push.connect('tcp://localhost:{port}'.format(port=self.frontend_port))
        
        # Our lock used to protect the frontend_push socket
        self.lock = threading.Lock()
        
    def setup(self, master):
        self.master = master
        self.start()
    
    def run(self):
        self.log.info("ZMQTaskScheduler started")
        # Start receiving messages
        try:
            zmq.proxy(self.frontend, self.backend)
        except zmq.ContextTerminated:
            pass
        except zmq.ZMQError:
            pass
        except:
            traceback.print_exc()

        self.frontend.close()
        self.backend.close()
        with self.lock:
            self.frontend_push.close()
        self.log.info("ZMQTaskScheduler stopped")
    
    def stop(self):
        self.context.term()
            
    def start_system(self, task_system):
        """
        Start an incomming task system
        """
        self.push_tasks(task_system.generate_tasks(self.master))
    
    def _push_task(self, task):
        """
        No lock variant of push task method
        """
        send_to_zmq_zipped(self.frontend_push, task)
        
    def push_tasks(self, tasks):
        """
        Push all tasks on the global task queue
        """
        with self.lock:
            # DO NOT USE push_task to queue tasks! It would be a deadlock!
            for task in tasks:
                self._push_task(task)
                #self.tasks.put(task)
    
    def push_task(self, task):
        """
        Put a task on the global task queue
        """
        with self.lock:
            # Do not poison ourselfs!
            if task:
                self._push_task(task)
                #self.tasks.put(task)
    
    def rate_slaves(self):
        """
        Update slaves
        """
        pass
    
    def _tasked_pushed(self, slave_id):
        """
        A slave has aquired a new task, update its rank
        """
        pass
    
    def task_finished(self, task, result, error):
        """
        A slave has finished a new task, update its rank
        """
        task.finished(result, error)

class AdvancedTaskManager(Component):
    implements(ITaskManager)
    """
    Advanced task manager which
    """
    
    #
    # Our async task update logic. This gets executed from our step
    # controller from the nodes main loop.
    # 
    # The update loop is composed by:
    #  - Generate task list
    #  - Execute task for current stat using current delta time and step count
    #  - Collect results and syncronize between systems (we still need to define what
    #    a system is, just a component that implements the system ExtensionPoint)
    #

    def update(self):
        """
        Update call from the frameworks main loop.
        """
        pass

    def _pre_execute(self):
        """
        Called before a step is exeuted
        """
        pass

    def _post_execute(self):
        """
        Called after a step has been performed
        """
        pass

    def _execute(self):
        """
        Execute a given step of the framework execution
        """
        pass




