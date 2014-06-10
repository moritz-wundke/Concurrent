# -*- coding: utf-8 -*-
"""
Module containing a slave node. Slaves are computation nodes
"""
from concurrent.core.components.component import Component, implements
from concurrent.core.application.api import IApp, SUCCESS_RET_CODES, APP_RET_CODE_FAILED
from concurrent.core.transport.simplejsonrpc import jsonremote
from concurrent.core.transport.tcpserver import tcpremote
from concurrent.core.async.api import ITaskScheduler
from concurrent.core.async.task import Task
from concurrent.core.config.config import BoolItem, ExtensionPointItem, HostItem, FloatItem, IntItem
from concurrent.core.async.threads import InterruptibleThread
from concurrent.framework.nodes.basenodes import ComputeNode, FailedToRegisterWithMaster

from collections import defaultdict
from bunch import Bunch

import urllib2
import time
import uuid
import web
import traceback

__all__ = ['SlaveNode']

class SlaveNode(Component, ComputeNode):
    implements(IApp)
    """
    A slave is a remote worker node that receives jobs from a master works them out and
    then returns the result to the master.
    """
    master_url = HostItem('slavenode', 'master', 'localhost:8080',
        """This slave master node""")
    
    def app_init(self):
        """
        Initialize application just before running it
        """
        super(SlaveNode, self).app_init()
        
        # We create our own node_id, this will be unique everywhere!
        self.node_id = uuid.uuid1()
        self.node_id_str = str(self.node_id)
        
        # Null this one first
        self.master_node_tcp = None

    def app_main(self):
        """
        Launch a concurrent application
        """
        result = super(SlaveNode, self).app_main()
        if result not in SUCCESS_RET_CODES:
            return result
        
        # Start computation
        try:
            self.setup_compute_node()
        except Exception:
            self.stop_compute_node()
            return APP_RET_CODE_FAILED
        
        # Flag used to re-create the master handshake if an unexpected connection drop
        # was detected
        self.unexected_connection_error = False
        self.is_registered = False
        
        # Enter app main loop
        self.main_loop()
        
        # Stop all processes and threads
        self.stop_compute_node()
        self.stop_api_thread()
        
        # Now launch base node
        return result
    
    def stop_compute_node(self):
        ComputeNode.stop_compute_node(self)
        try:
            self.unregister_from_master()
            self.master_node_tcp.close()
        except:
            traceback.print_exc()
            self.log.warn("Failed to close TCP compute channel with master!")
    
    # ---------------------------------------------------------------------
    # Master Node Registration
    # ---------------------------------------------------------------------
    
    def master_disconnected(self, gracefully):
        """
        Called when a master is disconnected (gracefully) or we had no response from the master itself (ungracefull)
        """
        self.log.info("Master disconnected (gracefully:%s)" % (gracefully))
        return True
    
    def get_master_url(self):
        """
        Get the URL where our master node is hosted
        """
        return "%s:%d" % (self.master_url)
    
    def has_master(self):
        """
        Check if the node has a master or not. Master node has no master itself
        """
        return True
    
    def generate_client_api(self):
        """
        Generate the client API of our compute channel
        """
        if self.master_node_tcp:
            @tcpremote(self.master_node_tcp_client)
            def push_task(handler, request, task):
                self.stats.add_avg('push_task')
                start = time.time()
                newTask = self.pickler.unpickle_s(task)
                ellapsed = time.time() - start
                self.stats.add_avg('push_task_unpickle_time',ellapsed)
                return self.push_task(newTask)
            
            @tcpremote(self.master_node_tcp_client)
            def register_slave_failed(handler, request, result):
                self.register_slave_failed(result)
            
            @tcpremote(self.master_node_tcp_client)
            def register_slave_response(handler, request, result):
                self.register_slave_response(result)
    
    def register_slave_failed(self, result):
        """
        Called when we failed to register ouselfs to a master node. Raises an exception.
        """
        raise FailedToRegisterWithMaster("Slave failed to register with the assigned master!")
    
    def register_slave_response(self, result):
        """
        Called when we finsihed to register ouselfs to a master node. Raises an exception if the master
        rejected us.
        """
        if not result:
            raise FailedToRegisterWithMaster("Master rejected our registration attempt!")
            
    def register_with_master(self):
        """
        The node will register itself with the expected master node
        """
        try:
            # Try to register with the master
            # TODO: Send all data the master requires to use the node best:
            #  - Processor information: Amount, type, cache, ...
            #  - RAM: Amount, speed, type, ECC?
            #  - GPU: Type of cards, OpenCL, Cuda, amount, speed, memory, ...
            #  - Net: Interface speed, connection speed, roundtrip, ...
            #  - OS: Os type, previledges, ...
            result = self.master_node.register_slave(self.node_id_str, self.port, {'workers':self.get_num_workers()})
            self.is_registered = True
            
            # if the node ID is we are getting from the master is different we are re-registering
            if result['id'] == self.node_id_str:
                self.node_id = uuid.UUID(result['id'])
                self.node_id_str = str(self.node_id)
            
            # Now we try to connect through our compute channel
            self.master_node_tcp, self.master_node_tcp_client = self.create_tcp_proxy(self.master_url[0], result['port'])
            self.generate_client_api()
            
            # Now connect
            self.master_node_tcp.connect()
            
            # No register us with the compute channel befor the master makes a timeout
            self.master_node_tcp.register_slave(self.node_id_str)
        except:
            traceback.print_exc()
            
    def unregister_from_master(self):
        """
        The node will unregister itself with the expected master node
        """
        if self.node_id:
            try:
                self.master_node.unregister_slave(self.node_id_str)
                self.master_node_tcp.close()
            except Exception as e:
                traceback.print_exc()
                self.log.error("Exception when unregistering from master: %s" % str(e))
            self.node_id = None
    
    def send_heartbeat(self):
        """
        Send heartbeat to master in case we have one
        """
        self.conditional_register_with_master()
        if self.node_id:
            try:
                self.is_registered = self.master_node.heartbeat_slave(self.node_id_str)
            except:
                pass
    
    def conditional_register_with_master(self):
        """
        Try to register with master after an unexpected connection failure
        """
        if not self.is_registered:
            try:
                self.register_with_master()
            except:
                pass
    
    def rpc_call_failed(self, proxy, method, reason):
        """
        Called when an RPC call failed for an unexpected reason
        """
        self.log.debug("Method %s failed because of %s" % (method, reason))
        
        # Handle network connection failures
        if urllib2.URLError == reason:
            self.unexected_connection_error = True
            self.is_registered = False
    
    def rpc_call_success(self, proxy, method, result):
        """
        Called when an RPC call succeded
        """
        self.log.debug("Method %s succeded with %s" % (method, result))
        self.unexected_connection_error = False
        
        return result
    
    # ---------------------------------------------------------------------
    # Task Handling
    # ---------------------------------------------------------------------
    
    def task_finished(self, task, result, error):
        """
        Called when a task has finished its computation, the result object contains the task, 
        the result or an error and additional information
        """
        try:
            self.master_node_tcp.task_finished(self.pickler.pickle_s(task), result, error)
            return True
        except:
            traceback.print_exc()
            return False