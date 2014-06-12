# -*- coding: utf-8 -*-
"""
Module containing the framework master node implementation
"""
from concurrent.core.components.component import Component, implements
from concurrent.core.application.api import IApp, SUCCESS_RET_CODES, APP_RET_CODE_FAILED
from concurrent.core.transport.simplejsonrpc import jsonremote
from concurrent.core.async.api import ITaskScheduler, ITaskSystem
from concurrent.core.async.task import Task
from concurrent.core.config.config import BoolItem, ExtensionPointItem, HostItem, FloatItem, IntItem
from concurrent.core.async.threads import InterruptibleThread
from concurrent.framework.nodes.basenodes import BaseNode, ComputeNode, NodeType, NodeState
from concurrent.core.transport.tcpserver import TCPServer, tcpremote, NoResponseRequired, TCPServerZMQ

from collections import defaultdict
from bunch import Bunch

import urllib2
import time
import uuid
import web
import traceback
import threading

__all__ = ['MasterNode']

class master_thread(InterruptibleThread):
    """
    The master thread is responsible to compile incomming applications, and handle long running tasks
    """
    def __init__(self, log):
        InterruptibleThread.__init__(self, log)
        self.kill_received = False
        
    def run(self):
        while not self.kill_received:
            pass
        self.log.info("master_thread exiting")
    
    def stop(self):
        try:
            self.kill_received = True
            self.join()
        except:
            pass
        self.log.info("master_thread stopped")

class MasterNode(Component, BaseNode):
    implements(IApp)
    """
    A MasterNode is a compute node that can act and be used in computation when in standalone mode
    but is mainly used to dsitribute jobs along registered slaves. Once the jobs of a slave, or
    its own, are finished we will redistribute the results to the responsible client nodes.
    """
    is_standalone = BoolItem('masternode', 'is_standalone', 'False',
        """Master node is also a slave and a standalone application""")
    
    inactivity_time_multiplier = IntItem('node', 'inactivity_time_multiplier', 3,
        """Inactivty multiplier multiplies the heartbeat time to ensure inactivity is always several heartbeats""")
    
    registry_mirror_timer = FloatItem('masternode', 'registry_mirror_timer', 30.0,
        """Timer used to update node registry mirror""")
    
    registry_cleanup_timer = FloatItem('masternode', 'registry_cleanup_timer', 60.0,
        """Timer used to cleanup the node registry""")
    
    task_scheduler= ExtensionPointItem('masternode', 'task_manager', ITaskScheduler, 'GenericTaskScheduler',
        """Task scheduler used by the master node""")
    
    master_port = IntItem('node', 'master_port', 8081,
        """Port used by the master node for high-performance communication and dedicated persistent connections""")
    
    def app_init(self):
        """
        Initialize application just before running it
        """
        super(MasterNode, self).app_init()
        
        # Start our TCPServer,
        #self.server = TCPServer("localhost", self.master_port, self)
        #self.server_thread = threading.Thread(name="tcp_server", target=self.server.serve_forever)
        #self.server_thread.daemon = True
        
        # Setup our ZeroMQ asyn server
        self.zmq_server = TCPServerZMQ(self.master_port, self.log, 5)
        
        # The node registry holds updated into about slaves/clients and its processing
        # we week track of number of tasks submitted to each slave, how they perform
        # general statistics and more.
        self.node_registry = defaultdict(self._default_node)
        self.registry_lock = self.lock_cache.registry_lock
        self.node_cleanup_threshold = self.registry_cleanup_timer
        self.task_scheduler.setup(self)
        
        # Our client registry
        self.client_registry = defaultdict(self._default_node)
        self.client_registry_lock = self.lock_cache.client_registry_lock
        
        # The registry mirror is used to send all updates from time to time and cache it.
        # We use a different dict so client status request do not block
        self.node_registry_mirror = {}
        self.registry_mirror_lock = self.lock_cache.registry_mirror_lock
        self.registry_mirror_threshold = self.registry_mirror_timer
        self.registry_mirror_dirty = True
        
        # Client registry mirror
        self.client_registry_mirror = {}
        self.client_registry_mirror_lock = self.lock_cache.client_registry_mirror_lock
        
        # Timer which controls inactivity handling of a node, being it a slave or a client
        self.inactivity_timer = self.heartbeat_timer*self.inactivity_time_multiplier
        self.inactivity_unregister_timer = self.inactivity_timer * 3
        self.inactivity_threshold = self.inactivity_timer
        
        self.test_timer = 1
        self.test_app_id = uuid.uuid1()
        
        # Our task system registry
        self.tasksystem_registry = defaultdict(self._default_tasksystem)
        self.tasksystem_lock = self.lock_cache.tasksystem_lock
        
        # Create master thread
        #self.master_thread = master_thread(self.log)
    
    def app_main(self):
        """
        Launch a concurrent application
        """
        self.log.info("Initializing MasterNode")
        result = super(MasterNode, self).app_main()
        if result not in SUCCESS_RET_CODES:
            return result

        # Start the main server thread
        #self.server_thread.start()
        self.zmq_server.start()
            
        # Enter mail loop
        self.main_loop()
        
        # Stop all threads processes
        #self.server.shutdown()
        self.zmq_server.stop()
        self.notify_shutdown()
        self.stop_api_thread()
        #self.stop_master_thread()
        self.task_scheduler.stop()        
        
        # Now launch base node
        return result
    
    def handle_echo(self, sock, address):
        print(address)
        fp = sock.makefile()
        while True:
            line = fp.readline()
            if line:
                fp.write(line)
                fp.flush()
            else:
                break
    
    def stop_master_thread(self):
        self.master_thread.stop()
         
    def generate_api(self):
        """
        Create all rpc methods the node requires
        """
        super(MasterNode, self).generate_api()
        if not self.is_standalone:
            @jsonremote(self.api_service_v1)
            def register_slave(request, node_id, port, data):
                self.stats.add_avg('register_slave')
                return self.register_node(node_id, web.ctx['ip'], port, data, NodeType.slave)
            
            @tcpremote(self.zmq_server, name='register_slave')
            #@tcpremote(self.server, name='register_slave')
            def register_slave_tcp(handler, request, node_id):
                self.stats.add_avg('register_slave_tcp')
                return self.register_node_tcp(handler, request, node_id, NodeType.slave)
            
            @jsonremote(self.api_service_v1)
            def register_client(request, node_id, port, data):
                self.stats.add_avg('register_client')
                return self.register_node(node_id, web.ctx['ip'], port, data, NodeType.client)
            
            @tcpremote(self.zmq_server, name='register_client')
            #@tcpremote(self.server, name='register_client')
            def register_client_tcp(handler, request, node_id):
                self.stats.add_avg('register_client_tcp')
                return self.register_node_tcp(handler, request, node_id, NodeType.client)
            
            @jsonremote(self.api_service_v1)
            def unregister_slave(request, node_id):
                self.stats.add_avg('unregister_slave')
                return self.unregister_node(node_id, NodeType.slave)
            
            @jsonremote(self.api_service_v1)
            def unregister_client(request, node_id):
                self.stats.add_avg('unregister_client')
                return self.unregister_node(node_id, NodeType.client)
            
            @jsonremote(self.api_service_v1)
            def heartbeat_slave(request, node_id):
                self.stats.add_avg('heartbeat_slave')
                return self.heartbeat(node_id, NodeType.slave)
            
            @jsonremote(self.api_service_v1)
            def heartbeat_client(request, node_id):
                self.stats.add_avg('heartbeat_client')
                return self.heartbeat(node_id, NodeType.client)
            
            @tcpremote(self.zmq_server)
            #@tcpremote(self.server)
            def task_finished(handler, request, task, result, error):
                self.stats.add_avg('task_finished')
                start = time.time()
                new_task = self.pickler.unpickle_s(task)
                ellapsed = time.time() - start
                self.stats.add_avg('task_finished_unpickle_time',ellapsed)
                self.task_finished(new_task, result, error)
                # This is an end method for the interaction
                raise NoResponseRequired()
            
            @tcpremote(self.zmq_server)
            #@tcpremote(self.server)
            def push_task_response(handler, request, result):
                # TODO: Handle failure when result is False!
                pass
            
            @tcpremote(self.zmq_server)
            #@tcpremote(self.server)
            def push_task_failed(handler, request, result):
                # TODO: Handle failure when pushing tasks failed!
                pass

        @tcpremote(self.zmq_server)
        #@tcpremote(self.server)
        def push_tasksystem(handler, request, tasksystem):
            """
            Push a application onto the computation framework
            """
            self.stats.add_avg('push_tasksystem')
            return self.push_tasksystem(request, self.pickler.unpickle_s(tasksystem))
    
    def _generate_status_dict(self, node):
        return {'type':node.type,'state':node.state}
    
    def status(self):
        status = ComputeNode.status(self)
        with self.registry_mirror_lock.readlock:
            status['nodes'] = dict((k, self._generate_status_dict(v)) for k, v in self.node_registry_mirror.iteritems() if v)
        with self.client_registry_mirror_lock.readlock:
            status['clients'] = dict((k, self._generate_status_dict(v)) for k, v in self.client_registry_mirror.iteritems() if v)
        return status
    
    def on_update(self, delta_time):
        super(MasterNode, self).on_update(delta_time)
        
        # Update map
        self.registry_mirror_threshold -= delta_time
        if self.registry_mirror_threshold < 0:
            self.update_registry_mirror()
            self.registry_mirror_threshold = self.registry_mirror_timer
        
        # Handle inactive nodes or cleanup empty nodes
        self.inactivity_threshold -= delta_time
        self.node_cleanup_threshold -= delta_time
        if self.inactivity_threshold < 0:
            self.update_inactive_nodes()
            self.inactivity_threshold = self.inactivity_timer
        elif self.node_cleanup_threshold < 0:
            self.clean_node_map()
            self.node_cleanup_threshold = self.registry_cleanup_timer
    
    def has_master(self):
        """
        Check if the node has a master or not. Master node has no master itself
        """
        return False
    
    def _handle_timeout(self, node):
        """
        Handle state for a given node checking the nodes timestamp value
        """
        ellapsed_time = self.current_time - node['heartbeat']
        if node['state'] == NodeState.active and ellapsed_time > self.inactivity_timer:
            self.log.info("Node %s set to inactive (t:%f)" % (node['node_id'], ellapsed_time))
            node['state'] = NodeState.inactive
            self.set_registry_dirty()
        elif node['state'] == NodeState.inactive and ellapsed_time > self.inactivity_unregister_timer:
            # Delete node! To much time inactive!
            self.log.info("Node %s kicked from system! To much time of inactivity! (t:%f)" % (node['node_id'], ellapsed_time))
            self.set_registry_dirty()
            return None
        return node
    
    def set_registry_dirty(self):
        """
        Set the registry dirty, this will force an update of the task scheduler
        """
        self.registry_mirror_dirty = True
        self.update_scheduler()
        
    def update_scheduler(self):
        """
        Update task scheduler with the current list of slaves
        """
        self.task_scheduler.rate_slaves()
        
    def update_inactive_nodes(self):
        """
        Called when we check for inactive nodes, those that have not send any heartbeat for a while
        """
        self.log.info("Checking for inactive nodes...") 
        with self.registry_lock.writelock:
            self.node_registry = dict((k, self._handle_timeout(v)) for k, v in self.node_registry.iteritems() if v)
        with self.client_registry_lock.writelock:
            self.client_registry = dict((k, self._handle_timeout(v)) for k, v in self.client_registry.iteritems() if v)
    
    def update_registry_mirror(self):
        """
        Update the registry mirror with a copy of the registry. Used to expose a copy dict to the public.
        """
        if self.registry_mirror_dirty:
            self.log.info("Updating node registry mirror...")
            with self.registry_mirror_lock.writelock:
                self.node_registry_mirror = dict((k, v) for k, v in self.node_registry.iteritems() if v)
            with self.client_registry_mirror_lock.writelock:
                self.client_registry_mirror = dict((k, v) for k, v in self.client_registry.iteritems() if v)
            self.registry_mirror_dirty = False
    
    def clean_node_map(self):
        """
        Clean node map for any empty node values.
        """
        self.log.info("Cleaning node registry...")
        with self.registry_lock.writelock:
            self.node_registry = dict((k, v) for k, v in self.node_registry.iteritems() if v)
        with self.client_registry_lock.writelock:
            self.client_registry = dict((k, v) for k, v in self.client_registry.iteritems() if v)
    
    def get_node_id_no_lock(self, url):
        return next((k for k, v in self.node_registry.iteritems() if v and v.url == url), None)
    
    def get_node_id(self, url):
        """
        Return a node id given an url
        """
        with self.registry_lock.readlock:
            node_id = self.get_node_id_no_lock(url)
        return node_id
    
    def get_client_id_no_lock(self, url):
        return next((k for k, v in self.client_registry.iteritems() if v and v.url == url), None)
    
    def get_client_id(self, url):
        """
        Return a client id given an url
        """
        with self.client_registry_lock.readlock:
            node_id = self.get_client_id_no_lock(url)
        return node_id
    
    def get_node(self, url):
        """
        Get a node representation given an url
        """
        node = None
        with self.registry_lock.readlock:
            node_id = self.get_node_id_no_lock(url)
            if node_id:
                node = self.node_registry[node_id]
        return node
    
    def get_client(self, url):
        """
        Get a node representation given an url
        """
        node = None
        with self.registry_lock.readlock:
            node_id = self.get_client_id_no_lock(url)
            if node_id:
                node = self.node_registry[node_id]
        return node
    
    def _default_node(self):
        return {}
    
    def _default_tasksystem(self):
        return Bunch({})
    
    def _default_slave_bunch(self):
        return Bunch({'node_id':'', 'url':'', 'ip':'', 'port':0, 'type':NodeType.slave, 'state':NodeState.inactive, 'heartbeat':0, 'proxy':None, 'workers':0, 'tasks':0, 'rating':0.0, 'handler': None})
    
    def _default_client_bunch(self):
        return Bunch({'node_id':'', 'url':'', 'ip':'', 'port':0, 'type':NodeType.slave, 'state':NodeState.inactive, 'heartbeat':0, 'proxy':None, 'handler': None})
    
    def register_node(self, node_id, ip, port, data, node_type):
        """
        Register a node within our node map
        """
        try:
            # TODO: CHECK ALL CLIENT DATA!
            url = ("%s:%d") % (ip, port)
            if NodeType.slave == node_type:
                with self.registry_lock.writelock:
                    node = self.get_node(url)
                    if node is None:
                        # This is a node that is registering again so reuse it
                        node = self.node_registry[node_id] = self._default_slave_bunch()
                    
                    # Basic node values
                    node.node_id = node_id
                    node.url = url
                    node.ip = ip
                    node.port = port
                    node.type = node_type
                    node.proxy = self.create_node_proxy(url)
                    node.state = NodeState.pending
                    node.heartbeat = time.time()
                    
                    # Add slave data                   
                    node.workers = data['workers']
                    node.tasks = 0
                    # Rating goes from [0, ..) 0 is the best rating and so asuitable candidate
                    node.rating = 0
                    node.handler = None
                    node.tcp_proxy = None
                    
                    # Make sure the mirror updates properly
                    self.set_registry_dirty()
                    
                    # Send back the generated id
                    return {'id': node.node_id, 'port': self.master_port}
            elif NodeType.client == node_type:
                with self.client_registry_lock.writelock:
                    node = self.get_node(url)
                    if node is None:
                        # This is a node that is registering again so reuse it
                        node = self.client_registry[node_id] = self._default_client_bunch()
                    
                    # Basic node values
                    node.node_id = node_id
                    node.url = url
                    node.ip = ip
                    node.port = port
                    node.type = node_type
                    node.proxy = self.create_node_proxy(url)
                    node.state = NodeState.pending
                    node.heartbeat = time.time()
                    
                    # Add client data
                    node.handler = None
                    node.tcp_proxy = None
                    
                    # Make sure the mirror updates properly
                    self.set_registry_dirty()
                    
                    # Send back the generated id
                    return {'id': node.node_id, 'port': self.master_port}
            else:
                raise NotImplementedError("Unkown node")
        except Exception as e:
            traceback.print_exc()
            # Make sure to cleanup node from node map!
            if node_id:
                self.unregister_node(node_id, node_type)
            raise e
    
    def unregister_node(self, node_id, node_type):
        """
        Unregister a node within our node map
        """
        if NodeType.slave == node_type:
            with self.registry_lock.writelock:
                if node_id in self.node_registry:
                    self.node_registry[node_id] = None
                    # Make sure we let the mirror update
                    self.registry_mirror_dirty = True
                    self.set_registry_dirty()
                    return True
                return False
        elif NodeType.client == node_type:
            with self.client_registry_lock.writelock:
                if node_id in self.client_registry:
                    # if we had a socket close it now!
                    self.client_registry[node_id] = None
                    # Get rid of any registered task system
                    with self.tasksystem_lock.writelock:
                        if node_id in self.tasksystem_registry:
                            del self.tasksystem_registry[node_id]
                    # Make sure we let the mirror update
                    self.registry_mirror_dirty = True
                    self.set_registry_dirty()
                    return True
                return False
        else:
            raise NotImplementedError("Unkown node")
    
    def register_node_tcp(self, handler, request, node_id, node_type):
        """
        Slave has just registered itself throug the compute channel
        """
        if NodeType.slave == node_type:
            with self.registry_lock.writelock:
                if node_id in self.node_registry:
                    # The handler is shared between many client sockets!
                    self.node_registry[node_id].handler = handler
                    self.node_registry[node_id].socket = handler.worker
                    self.node_registry[node_id].tcp_proxy = self.create_tcp_client_proxy(handler.worker, request)
                    self.node_registry[node_id].state = NodeState.active
                    # Let the slave know that the handshake worked
                    return True
                return False
        elif NodeType.client == node_type:
            with self.client_registry_lock.writelock:
                if node_id in self.client_registry:
                    # The handler is shared between many client sockets!
                    self.client_registry[node_id].handler = handler
                    self.client_registry[node_id].socket = handler.worker
                    self.client_registry[node_id].tcp_proxy = self.create_tcp_client_proxy(handler.worker, request)
                    self.client_registry[node_id].state = NodeState.active
                    # Safe some data within the handler itself
                    handler.node_id = node_id
                    handler.node_type = NodeType.client
                    # Let the client know that the handshake worked
                    return True
                return False
        else:
            raise NotImplementedError("Unkown node")
                    
            
        
    def notify_shutdown(self):
        """
        Notify a global shutdown to all nodes
        """
        with self.registry_lock.readlock:
            for node_id in self.node_registry:
                if self.node_registry[node_id] and self.node_registry[node_id].proxy:
                    try:
                        self.node_registry[node_id].proxy.master_disconnected()
                    except:
                        pass
        with self.client_registry_lock.readlock:
            for node_id in self.client_registry:
                if self.client_registry[node_id] and self.client_registry[node_id].proxy:
                    try:
                        self.client_registry[node_id].proxy.master_disconnected()
                    except:
                        pass
    
    def heartbeat(self, node_id, node_type):
        """
        We just received a nice beat from a node, update it's last heartbeat
        timestamp to perevent timeouts
        """
        if NodeType.slave == node_type:
            with self.registry_lock.writelock:
                if node_id in self.node_registry:
                    self.node_registry[node_id].heartbeat = time.time()
                    if self.node_registry[node_id].state == NodeState.inactive:
                        self.node_registry[node_id].state = NodeState.active
                    #self.log.info("Node %s just ticked" % (node_id))
                    return True
                return False
        elif NodeType.client == node_type:
            with self.client_registry_lock.writelock:
                if node_id in self.client_registry:
                    self.client_registry[node_id].heartbeat = time.time()
                    if self.client_registry[node_id].state == NodeState.inactive:
                        self.client_registry[node_id].state = NodeState.active
                    #self.log.info("Node %s just ticked" % (node_id))
                    return True
                return False
        else:
            raise NotImplementedError("Unkown node")
    
    def rpc_call_failed(self, proxy, method, reason):
        """
        Called when an RPC call failed for an unexpected reason
        """
        self.log.info("Method %s failed because of %s" % (method, reason))
    
    def rpc_call_success(self, proxy, method, result):
        """
        Called when an RPC call succeded
        """
        self.log.info("Method %s succeded with %s" % (method, result))
        return result
    
    def push_tasksystem(self, request, tasksystem):
        """
        We received a task system from a client. Get the first list of tasks and save out the
        system itself for later access
        """
        
        # Easier access
        node_id = request
        
        # Now get the
        with self.tasksystem_lock.writelock:
            # No re-registering!
            system_id = tasksystem.system_id
            if system_id in self.tasksystem_registry:
                return False
            
            # Safe out the registry
            system_entry = self.tasksystem_registry[system_id] = self._default_tasksystem()
            system_entry.system = tasksystem
            system_entry.client_id = node_id
            system_entry.system_id = system_id
            
            # Now gather task and push them to the system
            system_entry.system.init_system(self)
            self.task_scheduler.start_system(system_entry.system)
        return True
    
    def task_finished(self, task, result, error):
        """
        Called when a task has finished its computation, the result object contains the task, 
        the result or an error and additional information
        """        
        # Now pass the same result to the ITaskSystem that will handle the task
        with self.tasksystem_lock.readlock:
            if task.system_id in self.tasksystem_registry:
                system_entry = self.tasksystem_registry[task.system_id]
                system_entry.system.task_finished(self, task, result, error)
                
                # Inform scheduler of the task
                self.task_scheduler.task_finished(task, result, error)
                
                # Check for end
                if system_entry.system.is_complete(self):
                    with self.tasksystem_lock.writelock:
                        try:
                            # Gather results
                            final_results = system_entry.system.gather_result(self)
                            
                            # Send to client proxy the results
                            client_id = system_entry.client_id
                            with self.client_registry_lock.readlock:
                                if client_id in self.client_registry:
                                    self.client_registry[client_id].tcp_proxy.work_finished(final_results, self.pickler.pickle_s(system_entry.system))
                        finally:
                            del self.tasksystem_registry[task.system_id]
                                