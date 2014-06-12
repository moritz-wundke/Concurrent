# -*- coding: utf-8 -*-
"""
Module containing our base node enteties
"""

from concurrent.core.config.config import IntItem, ExtensionPointItem, ConfigItem, FloatItem, BoolItem
from concurrent.core.transport.simplejsonrpc import SimpleJSONRPCService, jsonremote
from concurrent.core.transport.gzipper import Gzipper
from concurrent.core.transport.tcpserver import TCPClient, TCPServerProxyZMQ#, TCPClientProxyZMQ
from concurrent.core.transport.tcpsocket import TCPSocket, send_to_zmq_multi
from concurrent.core.async.api import ITaskManager
from concurrent.core.async.threads import InterruptibleThread, ReadWriteLock, RWLockCache
from concurrent.core.application.api import APP_RET_CODE_SUCCESS, IPickler, NodeType, NodeState
from concurrent.core.util.stats import Stats
from concurrent.core.util.cryptohelper import CryptoHelper
import concurrent.core.transport.pyjsonrpc as pyjsonrpc

from bunch import Bunch

import sys
import web
import time
import traceback

__all__ = ['BaseNode', 'ComputeNode', 'NodeType', 'NodeState', 'FailedToRegisterWithMaster']

class FailedToRegisterWithMaster(Exception):
    """
    Exception raised when a node failed to register itself with the master node
    onto the compute channel.
    """
    
class NodeApp(web.application):
    """
    Web app for our node
    """
    def run(self, port, *middleware):
        func = self.wsgifunc(*middleware)
        return web.httpserver.runsimple(func, ('0.0.0.0', port))

class NodeProxy(object):
    """
    Make proxy calls async using a ThreadPool: http://www.chrisarndt.de/projects/threadpool/
    """
    def __init__(self, ProxyObject, log, ok_cb, ko_cb):
        self._obj=ProxyObject
        self.log = log
        self.ok_cb = ok_cb
        self.ko_cb = ko_cb
        self.stats = Stats.getInstance()
    
    class _Method(object):

        def __init__(self, owner, proxy_obj, method, log, ok_cb, ko_cb):
            self.owner = owner
            self._obj=proxy_obj
            self.method = method
            self.log = log
            self.ok_cb = ok_cb
            self.ko_cb = ko_cb

        def __call__(self, *args, **kwargs):
            try:
                start_time = time.time()
                result = self._obj.call(self.method, *args, **kwargs)
                self.owner.stats.add_avg('NodeProxy', time.time() - start_time)
                self.ok_cb(self._obj, self.method, result)
                return result
            except Exception as e:
                self.owner.stats.add_avg('NodeProxy', time.time() - start_time)
                self.ko_cb(self._obj, self.method, e)
                raise e
        
    def __call__(self, method, *args, **kwargs):
        try:
            start_time = time.time()
            result = self._obj.call(self.method, *args, **kwargs)
            self.owner.stats.add_avg('NodeProxy', time.time() - start_time)
            self.ok_cb(self._obj, self.method, result)
            return result
        except Exception as e:
            self.owner.stats.add_avg('NodeProxy', time.time() - start_time)
            self.ko_cb(self._obj, self.method, e)
            raise e
                
    def __getattr__(self, method):
        return self._Method(self, self._obj, method = method, log = self.log, ko_cb = self.ko_cb, ok_cb = self.ok_cb)
    
    def dump_stats(self):
        self.log.debug(self.stats.dump('NodeProxy'))

class TCPProxy(object):
    """
    TCP socket proxy using our JSON RPC protocol. The TCP proxy does not handle
    the answer from the given call, the answers are beeing received within the sockets
    own answer thread.
    """
    def __init__(self, ProxyObject, log):
        self._obj=ProxyObject
        self.log = log
        self.stats = Stats.getInstance()
    
    class _Method(object):

        def __init__(self, owner, proxy_obj, method, log):
            self.owner = owner
            self._obj=proxy_obj
            self.method = method
            self.log = log

        def __call__(self, *args, **kwargs):
            # Connect and close are very special
            if self.method == "close":
                self._obj.close()
            elif self.method == "connect":
                self._obj.connect()
            else:
                try:
                    start_time = time.time()
                    self._obj.send_to(self.method, *args, **kwargs)
                except Exception as e:
                    raise e
                finally:
                    self.owner.stats.add_avg('TCPProxy', time.time() - start_time)
        
    def __call__(self, method, *args, **kwargs):
        # Connect and close are very special
        if method == "close":
            self._obj.close()
        elif method == "connect":
            self._obj.connect()
        else:
            try:
                start_time = time.time()
                self._obj.send_to(self.method, *args, **kwargs)
            except Exception as e:
                raise e
            finally:
                self.owner.stats.add_avg('TCPProxy', time.time() - start_time)
                    
    def __getattr__(self, method):
        # Connect and close are very special
        return self._Method(self, self._obj, method = method, log = self.log)
    
    def dump_stats(self):
        self.log.debug(self.stats.dump('TCPProxy'))

class TCPProxyZMQ(object):
    """
    ZMQ client TCP socket proxy
    """
    def __init__(self, socket, identity, log):
        self.socket=socket
        self.identity=identity
        self.log = log
        self.stats = Stats.getInstance()
    
    class _Method(object):

        def __init__(self, owner, method, log):
            self.owner = owner
            self.method = method
            self.log = log

        def __call__(self, *args, **kwargs):
            if self.method != "close" and self.method != "connect":
                try:
                    start_time = time.time()
                    send_to_zmq_multi(self.owner.socket, self.owner.identity, self.method, *args, **kwargs)
                except Exception as e:
                    raise e
                finally:
                    self.owner.stats.add_avg('TCPProxyZMQ', time.time() - start_time)
        
    def __call__(self, method, *args, **kwargs):
        if method != "close" and method != "connect":
            try:
                start_time = time.time()
                send_to_zmq_multi(self.socket, self.identity, self.method, *args, **kwargs)
            except Exception as e:
                raise e
            finally:
                self.owner.stats.add_avg('TCPProxyZMQ', time.time() - start_time)
                    
    def __getattr__(self, method):
        # Connect and close are very special
        return self._Method(self, method = method, log = self.log)
    
    def dump_stats(self):
        self.log.debug(self.stats.dump('TCPProxy'))

class api_thread(InterruptibleThread):
    """
    Thread holding our JSON API server
    """
    def __init__(self, log, urls, port, use_gzip):
        InterruptibleThread.__init__(self, log)
        self.urls = urls
        self.port = port
        self.app = NodeApp(self.urls, globals())
        #self.app.internalerror = web.debugerror
        web.config.debug = False
        self.use_gzip = use_gzip
        self.gzipper = None
        
    def run(self):
        # Now launch our web app
        if self.use_gzip:
            self.app.run(self.port, Gzipper)
        else:
            self.app.run(self.port)
    
    def stop(self):
        try:
            self.app.stop()
            self.join()
        except:
            pass
        self.log.info("API Server Stopped")
        # Not a good idea though! stopping the server is enough!
        #self.stop_and_wait()

class GlobalHook(Bunch):
    """
    This is our global hook, used to save a reference to our global node
    """
global_hook = None

class index_get():
    """
    API index URL stub
    """    
    def GET(self):
        global global_hook
        return global_hook.node.index()

class ping_get():
    """
    API index URL stub
    """    
    def GET(self):
        global global_hook
        return global_hook.node.ping()

class status_get():
    """
    API index URL stub
    """    
    def GET(self):
        global global_hook
        return global_hook.node.status()

class stats_get():
    """
    API index URL stub
    """    
    def GET(self):
        global global_hook
        return global_hook.node.get_stats()

class APIHandlerV1():
    def POST(self):
        global global_hook
        if 'CONTENT_LENGTH' in web.ctx.env:
            global_hook.node.stats.add_avg('api1-content-length',int(web.ctx.env['CONTENT_LENGTH']))
        return global_hook.node.api_service_v1(web.webapi.data())

class BaseNode(object):
    """
    Base node, all nodes will be atleast of this type.
    Responsible for hosting and exposing a simple API
    apart from listening on a TCP port for socket interactions.
    """
    
    port = IntItem('node', 'port', 8080,
        """Port of the API interface with this node""")
    
    use_gzip = BoolItem('node', 'use_gzip', True,
        """Check if we should gzip all interactions (recommended)""")
    
    pickler = ExtensionPointItem('Node', 'pickler', IPickler, 'Pickler',
        """Pickler class used by the whole framework""")
    
    proxy_api = IntItem('node', 'proxy_api', 1,
        """API version used for any client JSON RPC calls""")
    
    proxy_username = ConfigItem('node', 'proxy_username', '',
        """Username used when performing API client calls""")
    
    proxy_password = ConfigItem('node', 'proxy_password', '',
        """Password used when performing API client calls""")
    
    heartbeat_timer = FloatItem('node', 'heartbeat_timer', 5.0,
        """Timer used to send periodically heartbeats to the master""")
    
    stats_dump_timer = FloatItem('node', 'stats_dump_timer', 30.0,
        """Timer used to dump stats into the log. -1 will never dump stats.""")
    
    secret = ConfigItem('node', 'crypot_secret', 'JhTv535Vg385V',
        """Default salt used on decrypting encrypting a pickle""")
    
    # salt size in bytes
    salt_size = IntItem('node', 'crypot_salt_size', 16,
        """Size of the salt used in the encryption process""")
    
    # number of iterations in the key generation
    num_iterations = IntItem('node', 'crypot_num_iterations', 20,
        """Number of iterations used in the key generation""")
    
    # the size multiple required for AES
    aes_padding = IntItem('node', 'crypot_aes_padding', 16,
        """Padding used for AES encryption""")
    
    urls = (
        # Get and basic API handling (not versioned!)
        '/', 'index_get'
        , '/ping/', 'ping_get'
        , '/ping', 'pint_get'
        , '/status/', 'status_get'
        , '/status', 'status_get'
        , '/stats/', 'stats_get'
        , '/stats', 'stats_get'
        # Post API handling of version 1
        , '/api/1/', 'APIHandlerV1'
        , '/api/1',  'APIHandlerV1'
    )
    
    def app_init(self):
        """
        Initialize application just before running it
        """
        self.lock_cache = RWLockCache()
        
    def app_main(self):
        """
        Launch a concurrent application
        """        
        # Generate rest API
        self.generate_api()
        
        # Now run our API listener
        self.log.debug("Hosting application on port %d" % (self.port))
        
        # Get a ref to our stats helper
        self.stats = Stats.getInstance()
        
        # Create cryto helper used for network communciation
        self.crypto_helper = CryptoHelper(self.salt_size, self.num_iterations, self.aes_padding)
        
        # Make sure the URL proxy knows us
        global global_hook
        global_hook = GlobalHook({'node':self})
        
        #api should only be there for the master node and used for node registration and heartbeats. Each node will have a socket
        #while slave nodes will have a local server too. There servers are no web servers because they are too expensive!
        
        #refactor server thingy tomorrow and add client which will be connected with the server through a normal socket!
        
        #The master server will act as only that, a controller and will distribute work using a better performing mechanism: UDP?
        
        #Use asycn calls for heartbeat for example
        
        #Create the server the same way the guys from PP do! (See ppserver) Try using a multithreaded pool to handle connections instead of threads!
        
        self.api_thread = api_thread(self.log, self.urls, self.port, self.use_gzip)
        self.api_thread.daemon = True
        self.api_thread.start()
        
        self.heartbeat_threshold = self.heartbeat_timer
        self.current_time = 0
        self.last_time = 0
        self.last_delta_time = 0
        
        self.stats_dump_threshold = self.stats_dump_timer
        
        # Bool flag used to control the main loop
        self.kill_received = False
        
        # Give us some time until its up
        time.sleep(0.5)
        return APP_RET_CODE_SUCCESS
        
    def stop_api_thread(self):
        self.api_thread.stop()
    
    def main_loop(self):
        # Register with master before anything
        if self.has_master():
            self.register_with_master()
        self.last_time = time.time()
        while not self.kill_received:
            try:
                # Calculate delta time for this frame
                self.current_time = time.time()
                delta_time = self.current_time - self.last_time
                self.on_update(delta_time)
                
                # Safe last time
                self.last_time = self.current_time
                self.last_delta_time = delta_time
            except KeyboardInterrupt:
                try:
                    if self.has_master():
                        self.unregister_from_master()
                except Exception as e:
                    traceback.print_exc()
                self.log.info("Exiting main loop")
                self.kill_received = True
            except Exception as e:
                traceback.print_exc()
                self.log.error("Mainloop exception: %s" % (e))
        self.log.info("Main loop exited!")
    
    def shutdown_main_loop(self):
        self.kill_received = True
    
    def on_update(self, delta_time):
        # Only dump is requested
        if self.stats_dump_timer > 0:
            self.stats_dump_threshold -= delta_time
            if self.stats_dump_threshold < 0:
                self.stats.dump_stats(self.log)
                self.stats_dump_threshold = self.stats_dump_timer
    
    def generate_api(self):
        # API service handler for version 1 (only version for now)
        self.api_service_v1 = SimpleJSONRPCService(api_version=1)
        
        @jsonremote(self.api_service_v1)
        def ping(request):
            return "pong"
        
        @jsonremote(self.api_service_v1)
        def status(request):
            return self.status()
        
        @jsonremote(self.api_service_v1)
        def api(request):
            return self.api_service_v1.api()
    
    def ping(self):
        return "pong"
        
    def index(self):
        return "OK"
    
    def status(self):
        status = {
                  'node':self.__class__.__name__
                  , 'systeminfo': self.compmgr.systeminfo
        }
        return status
    
    def get_stats(self):
        return self.stats.dump_all()
    
    def create_node_proxy(self, url):
        """
        Create a new json proxy instance used by the node when acting as a client role
        """
        return NodeProxy(pyjsonrpc.HttpClient( url = ("http://%s/api/%d") % (url,self.proxy_api), 
                              username = self.proxy_username, 
                              password = self.proxy_password ), self.log, 
                              self.rpc_call_success, self.rpc_call_failed)
    
    def create_tcp_proxy(self, host, port):
        """
        Create a JSON TCP socket proxy instance to a server
        """
        #tcp_client = TCPClient(self.log, host, port, self)
        #return TCPProxy(tcp_client, self.log), tcp_client
        tcp_client = TCPServerProxyZMQ(self.node_id_str, host, port, self.log)
        return TCPProxy(tcp_client, self.log), tcp_client
    
    def create_tcp_client_proxy(self, sock, request):
        """
        Create a JSON TCP socket proxy instance to a client
        """
        return TCPProxyZMQ(sock, request, self.log)
        #tcp_client = TCPClientProxyZMQ(self.node_id_str, host, port, self.log)
        #return TCPProxy(tcp_client, self.log), tcp_client
        
    # TODO: Make every node steam large amount of data over the normal socket: http://stackoverflow.com/questions/17667903/python-socket-receive-large-amount-of-data
    #  Control channel is over the API channel and real-time interactions over the TCP socket (see transport module)

class result_thread(InterruptibleThread):
    """
    Thread waiting for results from the workers
    """
    def __init__(self, log, result_queue, callback):
        InterruptibleThread.__init__(self, log)
        self.callback = callback
        self.result_queue = result_queue
        
    def run(self):
        while True:
            result = self.result_queue.get()
            if result is None:
                # A None task is used to shut us down
                self.result_queue.task_done()
                break
            self.result_queue.task_done()
            # If there was an error to send the result back queue it again
            if not self.callback(result.task, result.result, result.error):
                self.result_queue.put(result)
        self.log.info("result_thread exiting")
    
    def stop(self):
        try:
            self.result_queue.put(None)
            self.join()
        except:
            pass
        self.log.info("result_thread stopped")

class Node(BaseNode):
    """
    A simple node is a noce that has a master node. It handles the masters proxy and keeps it alive using
    heartbeats
    """
    
    def app_main(self):
        """
        Launch a concurrent application
        """
        super(Node, self).app_main()        
        self.setup_master()
    
    def on_update(self, delta_time):
        super(Node, self).on_update(delta_time)
        
        # Hanlde heartbeat
        self.heartbeat_threshold -= delta_time
        if self.has_master() and self.heartbeat_threshold < 0:
            self.send_heartbeat()
            self.heartbeat_threshold = self.heartbeat_timer
    
    def generate_api(self):
        super(Node, self).generate_api()
        
        @jsonremote(self.api_service_v1)
        def master_disconnected(request):
            return self.master_disconnected(True)
    
    def master_disconnected(self, gracefully):
        """
        Called when a master is disconnected (gracefully) or we had no response from the master itself (ungracefull)
        """
        raise NotImplementedError("Node has not implemented master_disconnected!")
    
    def get_master_url(self):
        """
        Get the URL where our master node is hosted
        """
        raise NotImplementedError("Node has not implemented get_master_url!")
    
    def setup_master(self):
        """
        Nodes that state to have a master should now create the master proxy
        """
        self.master_node = self.create_node_proxy(self.get_master_url())
    
    def register_with_master(self):
        """
        The node will register itself with the expected master node
        """
        raise NotImplementedError("Node has not implemented register_node!")
    
    def unregister_from_master(self):
        """
        The node will unregister itself with the expected master node
        """
        raise NotImplementedError("Node has not implemented unregister_node!")
    
    def send_heartbeat(self):
        """
        Send heartbeat to master in case we have one
        """
        raise NotImplementedError("Node has not implemented send_heartbeat!")
    
    def rpc_call_failed(self, proxy, method, reason):
        """
        Called when an RPC call failed for an unexpected reason
        """
        raise NotImplementedError("Node has not implemented rpc_call_failed!")
    
    def rpc_call_success(self, proxy, method, result):
        """
        Called when an RPC call succeded
        """
        raise NotImplementedError("Node has not implemented rpc_call_success!")
        return result
    
class ComputeNode(Node):
    """
    A compute node is a base node that does computation. It features a set of worker
    processes that except jobs from, usually a MasterNode.
    """    
    task_manager = ExtensionPointItem('computenode', 'task_manager', ITaskManager, 'GenericTaskManager',
        """Task manager used by this compute node""")
    
    def setup_compute_node(self):
        """
        Launch the compute service from this node
        """
        self.log.info("Initializing ComputeNode")
        self.task_manager.init();
        self.task_manager.start();
        
        # Start results collector thread
        self.collector_thread = None
        self.collector_thread = result_thread(self.log, self.task_manager.get_results_queue(), self.task_finished)
        self.collector_thread.daemon = True
        self.collector_thread.start()
    
    def stop_compute_node(self):
        self.task_manager.stop()
        if self.collector_thread:
            self.collector_thread.stop()
    
    def task_finished(self, task, result, error):
        """
        Called when a task has finished its computation, the result object contains the task, 
        the result or an error and additional information
        """
        raise NotImplemented("Node must implement the on_result callback function")
        return False
    
    def get_num_workers(self):
        """
        Return the number of workers the compute node has spawned
        """
        return self.task_manager.get_num_workers()
    
    def generate_api(self):
        """
        Create all rpc methods the node requires
        """
        super(ComputeNode, self).generate_api()
        @jsonremote(self.api_service_v1, doc='Push a task onto the computation node')
        def push_task(request, task):
            self.stats.add_avg('push_task')
            start = time.time()
            newTask = self.pickler.unpickle_s(task)
            ellapsed = time.time() - start
            self.stats.add_avg('push_task_unpickle_time',ellapsed)
            return self.push_task(newTask)
    
    def push_task(self, task):
        """
        Push a task onto the computation framework
        """
        return self.task_manager.push_task(task)