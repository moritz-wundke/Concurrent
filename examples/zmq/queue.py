import sys
import zmq
from  multiprocessing import Process, Queue
import time
 
def worker_zmq():
    context = zmq.Context()
    work_receiver = context.socket(zmq.PULL)
    work_receiver.connect("tcp://127.0.0.1:5557")
 
    for task_nbr in range(10000000):
        message = work_receiver.recv()
 
    sys.exit(1)
 
def main_zmq():
    Process(target=worker_zmq, args=()).start()
    context = zmq.Context()
    ventilator_send = context.socket(zmq.PUSH)
    ventilator_send.bind("tcp://127.0.0.1:5557")
    for num in range(10000000):
        ventilator_send.send("MESSAGE")
 
def worker(q):
    for task_nbr in range(10000000):
        message = q.get()
    sys.exit(1)
  
def main():
    send_q = Queue()
    Process(target=worker, args=(send_q,)).start()
    for num in range(10000000):
        send_q.put("MESSAGE")
 
if __name__ == "__main__":
    start_time = time.time()
    main_zmq()
    end_time = time.time()
    duration = end_time - start_time
    msg_per_sec = 10000000 / duration
 
    print "(ZMQ) Duration: %s" % duration
    print "(ZMQ) Messages Per Second: %s" % msg_per_sec

    start_time = time.time()
    main()
    end_time = time.time()
    duration = end_time - start_time
    msg_per_sec = 10000000 / duration
 
    print "Duration: %s" % duration
    print "Messages Per Second: %s" % msg_per_sec
