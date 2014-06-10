import zmq
import sys
import threading
import time
import zlib
from random import randint, random
try: import cPickle as pickle
except ImportError: import pickle

__author__ = "Felipe Cruz <felipecruz@loogica.net>"
__license__ = "MIT/X11"

def tprint(msg):
    """like print, but won't get newlines confused with multiple threads"""
    sys.stdout.write(msg + '\n')
    sys.stdout.flush()

def pickle_object(obj, protocol=2):
    """
    Pickle an object to be send over the network
    """
    p = pickle.dumps(obj, protocol)
    return zlib.compress(p)

def unpickle_message(msg):
    """
    Unpickle a message received from the network
    """
    p = zlib.decompress(msg)
    return pickle.loads(p)

class ClientTask(threading.Thread):
    """ClientTask"""
    def __init__(self, id, host, port):
        self.id = u'client-%d' % id
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.DEALER)
        self.host = host
        self.port = port
        threading.Thread.__init__ (self)

    def run(self):
        #context = zmq.Context()
        #socket = context.socket(zmq.DEALER)
        self.socket.identity = self.id.encode('ascii')
        self.socket.connect('tcp://{host}:{port}'.format(host=self.host, port=self.port))
        print('Client %s started' % (self.id))
        poll = zmq.Poller()
        poll.register(self.socket, zmq.POLLIN)
        reqs = 0
        while True:
            reqs = reqs + 1
            print('Req #%d-%s sent..' % (reqs, self.id))
            self.socket.send(pickle_object(u'request #%d-%s' % (reqs, self.id)))
            for i in range(5):
                sockets = dict(poll.poll(1000))
                if self.socket in sockets:
                    msg = unpickle_message(self.socket.recv())
                    tprint('Client %s received: %s' % (self.id, msg))

        self.socket.close()
        self.context.term()

class ServerTask(threading.Thread):
    """ServerTask"""
    def __init__(self, port):
        threading.Thread.__init__ (self)
        self.port = port

    def run(self):
        context = zmq.Context()
        frontend = context.socket(zmq.ROUTER)
        frontend.bind('tcp://*:{port}'.format(port=self.port))

        backend = context.socket(zmq.DEALER)
        backend.bind('inproc://backend')

        workers = []
        for i in range(1):
            worker = ServerWorker(context)
            worker.start()
            workers.append(worker)

        poll = zmq.Poller()
        poll.register(frontend, zmq.POLLIN)
        poll.register(backend,  zmq.POLLIN)

        while True:
            sockets = dict(poll.poll())
            if frontend in sockets:
                ident, msg = frontend.recv_multipart()
                msg = unpickle_message(msg)
                tprint('Server received %s id %s' % (msg, ident))
                backend.send_multipart([ident, pickle_object(msg)])
            if backend in sockets:
                ident, msg = backend.recv_multipart()
                msg = unpickle_message(msg)
                tprint('Sending to frontend %s id %s' % (msg, ident))
                frontend.send_multipart([ident, pickle_object(msg)])

        frontend.close()
        backend.close()
        context.term()

class ServerWorker(threading.Thread):
    """ServerWorker"""
    def __init__(self, context):
        threading.Thread.__init__ (self)
        self.context = context

    def run(self):
        worker = self.context.socket(zmq.DEALER)
        worker.connect('inproc://backend')
        tprint('Worker started')
        while True:
            ident, msg = worker.recv_multipart()
            msg = unpickle_message(msg)
            tprint('Worker received %s from %s' % (msg, ident))
            replies = randint(0,4)
            for i in range(replies):
                time.sleep(1. / (randint(1,10)))
                worker.send_multipart([ident, pickle_object(msg)])

        worker.close()

def main():
    """main function"""
    port = 8081 #5570
    server = ServerTask(port)
    server.start()
    for i in range(3):
        client = ClientTask(i, 'localhost', port)
        client.start()

    server.join()

if __name__ == "__main__":
    main()
