#
# Thread benchmark
#
import unittest
import time
import threading
import multiprocessing

class TestBenchmarkThreads(unittest.TestCase):

    def setUp(self):
        pass

    def count(self, n):
        while n > 0:
            n -= 1
    def test_benchmark_sequential(self):
        start = time.time()
        self.count(10000000)
        self.count(10000000)
        end = time.time()
        #print ("Sequential", end-start)

    def test_benchmark_threaded(self):
        start = time.time()
        t1 = threading.Thread(target=self.count,args=(10000000,))
        t2 = threading.Thread(target=self.count,args=(10000000,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        end = time.time()
        #print ("Threaded", end-start)

    def test_benchmark_processes(self):
        start = time.time()
        p1 = multiprocessing.Process(target=self.count,args=(10000000,))
        p2 = multiprocessing.Process(target=self.count,args=(10000000,))
        p1.start()
        p2.start()
        p1.join()
        p2.join()
        end = time.time()
        #print ("Multiprocessing", end-start)


if __name__ == '__main__':
    unittest.main()
