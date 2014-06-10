# -*- coding: utf-8 -*-
"""
Implementation of our socket server
"""

from concurrent.core.transport.tcpsocket import send_to, receive_from, send_to_zmq_zipped, send_to_zmq_multi, pickle_object, unpickle_message, VERSION, NoDataException, TCPSocket, TCPSocketZMQ
from concurrent.core.transport.pyjsonrpc.rpcerror import JsonRpcError
from concurrent.core.async.threads import InterruptibleThread
from concurrent.core.util.utils import tprint

import SocketServer
import threading
import traceback
import time
import socket
import errno
import zmq

__all__ = ['ThreadedSocketServer', 'tcpremote', 'TCPHandler', 'TCPServer', 'TCPClient']

class NoResponseRequired(Exception):
    """
    Exception raised when the executed method does not require a response. Used for Fire and 
    forget methods.
    """
 
class ThreadedTCPRequestHandler(SocketServer.BaseRequestHandler):
    def __init__(self, request, client_address, server):
        SocketServer.BaseRequestHandler.__init__(self, request, client_address, server)
        
    def setup(self):
        self.shutdown = False
        self.initial_connection = time.time()        
        self.server.client_connected(self.request, self.client_address, self)
        self.node_id = None
        self.node_type = None
        
    def handle(self):
        while not self.shutdown:
            # Decode data from socket
            try:
                send_to(self.request, *self.server.handle(self, self.request, receive_from(self.request)))
            except NoDataException:
                # No data means that there where nothign to read for and so the socket is dead
                self.shutdown = True
            except socket.error as e:
                if e.errno == errno.EINTR:
                    continue
                break
            except NoResponseRequired:
                # Method does not require a response to the socket, this is actually fine ^^
                pass
            except KeyboardInterrupt:
                break
            except:
                traceback.print_exc()
                # Not really good to just pass but saver for now!
                pass
        try:
            # Close socket just in case we let the resource open
            if self.request:
                self.request.close()
        except:
            # Not really an issue at this point
            pass
    
    def close(self):
        self.shutdown = True
    
    def finish(self):
        self.server.client_disconnected(self.request, self.client_address, self)
    
    def set_node_id(self, node_id, node_type):
        """
        Set the node_id used by this handler to link it to a registered node
        """
        self.node_id = node_id
        self.node_type = node_type

class TCPHandler(object):
    """
    Very simple TCP protocol handler that translates incomming request to function calls
    """
    
    def __init__(self):
        object.__init__(self)
        self.method_map = {}
    
    def add_method(self, name, method):
        self.method_map[name] = method
    
    def handle_rpc(self, handler, request, data):
        try:
            # TODO: Error handling, we will have the 'e' field within our data dict
            # TODO: Handle return of a simple ping-pong call to stop calling the client. (NoResponseRequired)
            v, method, params = data["v"], data["m"], [handler, request] + list(data["p"])
            #print(method)
            if v != VERSION:
                return "{}_failed".format(method), {"c": -32600, "m": "Invalid Request"},
            if method in self.method_map:
                try:
                    result = self.method_map[method](*params)
                    # No ping-pong for response calls
                    if method.endswith('_failed') or method.endswith('_response'):
                        raise NoResponseRequired()
                except JsonRpcError as e:
                    return "{}_failed".format(method), {"c": e.code, "m": e.message},
                except TypeError:
                    return "{}_failed".format(method), {"c": -32602, "m": "Invalid params"},
                return "{}_response".format(method), result
            else:
                # If the methods was not found and it was a fail or a response message just stop here
                if method.endswith('_failed') or method.endswith('_response'):
                    raise NoResponseRequired()
                return "{}_failed".format(method), {"c": -32601, "m": "Method not found"},
        except KeyError:
            if method:
                return "{}_failed".format(method), {"c": -32700, "m": "Parse error"},
            raise NoResponseRequired()
        except TypeError:
            #traceback.print_exc()
            if method:
                return "{}_failed".format(method), {"c": -32600, "m": "Invalid Request"},
            raise NoResponseRequired()
        except NoResponseRequired as e:
            # Fire up
            raise e
        except Exception as e:
            if method:
                return "{}_failed".format(method), {"c": -32603, "m": "Internal error", "e": e, "t": traceback.format_exc()},
            raise NoResponseRequired()
    
    def handle(self, handler, request, data):
        return self.handle_rpc(handler, request, data)

class TCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer, TCPHandler):
    """
    Our threaded socket implementation is a JSON-RPC implementation using a SocketServer. We use this
    technique to be able to achieve high-performance in connectivity and sync between all nodes while
    being felxible and simple within our data interaction.
    """
    
    daemon_threads = True
    allow_reuse_address = True
    
    def __init__(self, host, port, master):
        SocketServer.TCPServer.__init__(self, (host, port), ThreadedTCPRequestHandler)
        TCPHandler.__init__(self)
        self.master = master

    def client_connected(self, request, client_address, handler):
        print('{}:{} connected'.format(*client_address))
    
    def client_disconnected(self, request, client_address, handler):
        print('{}:{} disconnected'.format(*client_address))

class client_thread(InterruptibleThread):
    """
    The client thread of a socket reads in a nice loop any response that comes from the server connection
    """
    def __init__(self, tcp_client, log):
        InterruptibleThread.__init__(self, log)
        self.shutdown = False
        self.tcp_client = tcp_client
        
    def run(self):
        while not self.shutdown:
            # Decode data from socket
            try:
                self.tcp_client.send_to(*self.tcp_client.handle(self.tcp_client, self.tcp_client.sock, self.tcp_client.receive_from()))
            except NoDataException:
                # No data means that there where nothign to read for and so the socket is dead
                self.shutdown = True
            except socket.error as e:
                if e.errno == errno.EINTR:
                    continue
                break
            except NoResponseRequired:
                # Method does not require a response to the socket, this is actually fine ^^
                pass
            except KeyboardInterrupt:
                break
            except:
                traceback.print_exc()
                # Not really good to just pass but saver for now!
                pass
        try:
            # Close socket just in case we let the resource open
            if self.tcp_client.sock:
                self.tcp_client.sock.close()
        except:
            # Not really an issue at this point
            pass
        self.log.info("client_thread exiting")
    
    def stop(self):
        try:
            if self.tcp_client.sock:
                self.tcp_client.sock.close()
        except:
            pass
        self.shutdown = True
        # Not the best way but the safest... we can not wait for the server on termination.
        self.stop_and_wait()
        self.log.info("client_thread stopped")

class TCPClient(TCPSocket, TCPHandler):
    """
    TCP client used to map protocol calling mechanisms to a given function. Just
    a special socket that does apart from sending and receiving the translation
    of our protocol.
    """
    def __init__(self, log, host, port, node, socket1=None, socket_timeout=None):
        TCPSocket.__init__(self, host, port, node, socket1, socket_timeout)
        TCPHandler.__init__(self)
        self.master_thread = None
        self.log = log
    
    def connect(self):
        """Connect and start the client thread to listen for responses"""
        TCPSocket.connect(self)
        self.master_thread = client_thread(self, self.log)
        self.master_thread.start()
    
    def close(self):
        """Close socket connection and client thread"""
        try:
            TCPSocket.close(self)
        finally:
            # Alwasy stop the client thread!
            self.master_thread.stop()

#try this: http://zguide.zeromq.org/py:mtserver
#and this to optimize our IPC calls! http://taotetek.net/2011/02/03/python-multiprocessing-zeromq-vs-queue/

class TCPServerZMQ(threading.Thread, TCPHandler):
    """
    TCP ZeroMQ async server. Spawns a number of workers that will respond to client
    requests 
    """
    
    def __init__(self, port, log, num_workers=5):
        threading.Thread.__init__ (self)
        self.log = log
        
        # Some thread related stuff
        self.daemon = True
        self.kill_switch = False
        
        # The frontend is where we get the request from outside
        # we will route them to our workers to get processed
        self.port = port
        self.num_workers = num_workers
        self.workers = []
        self.context = zmq.Context()
        self.frontend = self.context.socket(zmq.ROUTER)
        self.frontend.bind('tcp://*:{port}'.format(port=self.port))
        
        # The backedn is where we queue the requests that the workers
        # will start working on in round robbin fashion
        self.backend = self.context.socket(zmq.DEALER)
        self.backend.bind('inproc://backend')
        
        # The poller is used to poll for incomming messages for both
        # the frontend (internet) and the backend (scheduling)
        self.poll = zmq.Poller()
        self.poll.register(self.frontend, zmq.POLLIN)
        self.poll.register(self.backend,  zmq.POLLIN)

    def stop(self):
        """
        Stop server and workers
        """
        self.log.info("Shutting down TCPServerZMQ")
        self.kill_switch = True
        for worker in self.workers:
            worker.stop()
        self.join(5000)
        self.log.info(" Done")
    
    def add_method(self, name, method):
        # We will just pass the handle to our workers
        for worker in self.workers:
            worker.add_method(name, method)

    def run(self):
        self.log.info("TCPServerZMQ started")
        # Create and launch workers
        for i in range(self.num_workers):
            worker = TCPServerZMQWorker(self.context, self.log)
            worker.start()
            self.workers.append(worker)  
                
        # Start receiving messages
        while self.kill_switch:
            sockets = dict(self.poll.poll(1000))
            if self.frontend in sockets:
                ident, msg = self.frontend.recv_multipart()
                tprint('Server received message from %s' % (ident))
                self.backend.send_multipart([ident, msg])
            if self.backend in sockets:
                ident, msg = self.backend.recv_multipart()
                tprint('Sending message back to %s' % (ident))
                self.frontend.send_multipart([ident, msg])

        self.frontend.close()
        self.backend.close()
        self.context.term()

class TCPServerZMQWorker(threading.Thread, TCPHandler):
    """ServerWorker"""
    def __init__(self, context, log):
        threading.Thread.__init__ (self)
        TCPHandler.__init__(self)
        self.log = log        
        
        # Worker stuff
        self.context = context
        self.worker = self.context.socket(zmq.DEALER)
        
        # Some thread related stuff
        self.daemon = True
        self.kill_switch = False
        
    def run(self):
        self.worker.connect('inproc://backend')
        self.log.info("TCPServerZMQWorker started")
        while self.kill_switch:
            # Receive message and unpickle it
            ident, msg = self.worker.recv_multipart()
            msg = unpickle_message(msg)
            tprint('Worker received %s from %s' % (msg, ident))
            
            # Handle message
            result = self.handle(self, ident, msg)            
            
            # Send back to router
            self.worker.send_multipart([ident, pickle_object(result)])
        
        self.worker.close()
    
    def stop(self):
        self.log.info("Shutting down TCPServerZMQWorker")
        self.kill_switch = True
        self.worker.close()
        self.join(1000)
        self.log.info(" Closed")
        
class TCPClientZMQ(TCPSocketZMQ, threading.Thread, TCPHandler):
    """
    TCP client using the ZeroMQ network framework
    """
    def __init__(self, identity, host, port, log):
        TCPSocketZMQ.__init__(self, identity, host, port)
        TCPHandler.__init__(self)
        threading.Thread.__init__ (self)
        self.log = log
        
        # Some thread related stuff
        self.daemon = True
        self.kill_switch = False
    
    def connect(self):
        """Connect and start the client thread to listen for responses"""
        self.start()
        
    def close(self):
        """Close socket connection and client thread"""
        try:
            TCPSocket.close(self)
        finally:
            # Alwasy stop the client thread!
            self.stop()
            
    def run(self):
        TCPSocket.connect(self)
        # Before starting create socket poll
        self.poll = zmq.Poller()
        self.poll.register(self.socket, zmq.POLLIN)
        while self.kill_switch:
            sockets = dict(self.poll.poll(1000))
            if self.socket in sockets:
                msg = unpickle_message(self.socket.recv())
                result = self.handle(self, self.identity, msg)
                self.socket.send(pickle_object(result))
        
        # Close socket
        self.close()
    
    def stop(self):
        """
        Stop socket and thread
        """
        self.log.info("Shutting down TCPClientZMQ")
        self.kill_switch = True
        self.join(1000)
        self.log.info(" Closed")
        

def tcpremote(tcp_opbject, name=None):
    """
    makes TCPServer or TCPClient a decorator so that you can write :
    
    from tcpserver import *

    server = TCPServer(...)

    @tcpremote(server, name='login')
    def login(request, client_address, user_name, user_pass):
        (...)
    
    """
    
    def remotify(func):
        if isinstance(tcp_opbject, TCPHandler):
            func_name = name
            if func_name is None:
                func_name = func.__name__
            tcp_opbject.add_method(func_name, func)
        else:
            raise NotImplementedError('Server "%s" not an instance of TCPServer' % str(tcp_opbject))
        return func

    return remotify