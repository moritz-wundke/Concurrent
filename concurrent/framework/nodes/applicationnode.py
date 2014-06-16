# -*- coding: utf-8 -*-
"""
Module containing a client node. Client nodes are the work requestor
"""
from concurrent.core.components.component import Component, implements
from concurrent.core.application.api import IApp, SUCCESS_RET_CODES, APP_RET_CODE_FAILED
from concurrent.core.transport.simplejsonrpc import jsonremote
from concurrent.core.transport.tcpserver import tcpremote, NoResponseRequired
from concurrent.core.async.api import ITaskScheduler, ITaskSystem
from concurrent.core.async.task import Task
from concurrent.core.config.config import BoolItem, ExtensionPointItem, HostItem, FloatItem, IntItem
from concurrent.core.async.threads import InterruptibleThread
from concurrent.framework.nodes.basenodes import Node, FailedToRegisterWithMaster

from collections import defaultdict
from bunch import Bunch

import urllib2
import time
import uuid
import web
import traceback

__all__ = ['ApplicationNode']

# TODO
# ------------------------------------------------------------------
#  - Multi ITaskSystem
#  - Stats for whole system and each task
#  - Read-Time stats in master and in slaves to see what is going on
#  - Finish rest of the examples
#  - Move common code for app and slave nodes into Node

class ApplicationNode(Component, Node):
    implements(IApp)
    """
    An application node is a consumer node of the framework
    """
    master_url = HostItem('applicationnode', 'master', 'localhost:8080',
        """This slave master node""")
    
    def app_init(self):
        """
        Initialize application just before running it
        """
        super(ApplicationNode, self).app_init()
        
        # Null this one first
        self.master_node_tcp = None
        
    def app_main(self):
        """
        Launch a concurrent application
        """
        result = super(ApplicationNode, self).app_main()
        if result not in SUCCESS_RET_CODES:
            return result
        
        # Flag used to re-create the master handshake if an unexpected connection drop
        # was detected
        self.unexected_connection_error = False
        self.is_registered = False
        
        # Make sure we clear the system out
        self.task_system = None
        
        # Enter app main loop
        self.main_loop()
        
        # Stop all processes and threads
        self.stop_app_node()
        self.stop_api_thread()
        
        # Now launch base node
        return result
    
    def stop_app_node(self):
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
    
    def get_master_address(self):
        """
        Get the adress and port in (host,port) fashion
        """
        return ('localhost',8081)
    
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
            def work_finished(handler, request, result, task_system):
                self.work_finished(result, self.pickler.unpickle_s(task_system))
                raise NoResponseRequired()
            
            @tcpremote(self.master_node_tcp_client)
            def push_tasksystem_failed(handler, request, result):
                self.push_tasksystem_failed(result)
            
            @tcpremote(self.master_node_tcp_client)
            def push_tasksystem_response(handler, request, result):
                self.push_tasksystem_response(result)
            
            @tcpremote(self.master_node_tcp_client)
            def register_client_failed(handler, request, result):
                self.register_client_failed(result)
            
            @tcpremote(self.master_node_tcp_client)
            def register_client_response(handler, request, result):
                self.register_client_response(result)
    
    def work_finished(self, result, task_system):
        """
        Called when the work has been done, the results is what our ITaskSystem
        sent back to us. Check resukt for more info
        """
        raise NotImplementedError("Node has not implemented work_finished!")
    
    def push_tasksystem_response(self, result):
        """
        We just added a ITaskSystem on the framwork. Check result for more info
        """
        raise NotImplementedError("Node has not implemented push_tasksystem_response!")
    
    def push_tasksystem_failed(self, result):
        """
        We failed to push a ITaskSystem on the computation framework!
        """
        raise NotImplementedError("Node has not implemented push_tasksystem_failed!")

    def register_client_failed(self, result):
        """
        Called when we failed to register ouselfs to a master node. Raises an exception.
        """
        raise FailedToRegisterWithMaster("Client failed to register with the assigned master!")
    
    def register_client_response(self, result):
        """
        Called when we finsihed to register ouselfs to a master node. Raises an exception if the master
        rejected us.
        """
        if not result:
            raise FailedToRegisterWithMaster("Master rejected our registration attempt!")
        
        # Now that we are registered we can start sending the application to the master and start processing it,
        # if this is a re-register we hope that the computation has not yet been completed!
        if self.task_system is None:
            self._start_processing()
    
    def register_with_master(self):
        """
        The node will register itself with the expected master node
        """
        try:
            # Try to register with the master
            result = self.master_node.register_client(self.node_id_str, self.port, {})
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
            self.master_node_tcp.register_client(self.node_id_str)
        except:
            pass
            
    def unregister_from_master(self):
        """
        The node will unregister itself with the expected master node
        """
        if self.node_id:
            try:
                self.master_node.unregister_client(self.node_id_str)
            except Exception as e:
                self.log.error("Exception when unregistering from master: %s" % str(e))
            self.node_id = None
    
    def send_heartbeat(self):
        """
        Send heartbeat to master in case we have one
        """
        self.conditional_register_with_master()
        if self.node_id:
            try:
                self.is_registered = self.master_node.heartbeat_client(self.node_id_str)
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
    # ITaskSystem Handling
    # ---------------------------------------------------------------------
    
    def get_task_system(self):
        """
        Called from the base class when we are connected to a MasterNode and we are 
        able to send computation tasks over
        """
        raise NotImplementedError("Node has not implemented get_task_system!")
    
    def _start_processing(self):
        """
        Called once the application is registered with the framework and we 
        are ok to start our processing!
        """
        # Request task system instance
        
        self.task_system = self.get_task_system()
        
        # Make sure its an instance of ITaskSystem
        if not isinstance(self.task_system, ITaskSystem):
            raise NotImplementedError('TaskSystem "%s" not an instance of ITaskSystem' % str(self.task_system))
        
        # Pickle and send!        
        self.master_node_tcp.push_tasksystem(self.pickler.pickle_s(self.task_system))
    
    