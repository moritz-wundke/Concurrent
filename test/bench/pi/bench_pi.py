#
# Cython vs Pure Python benchmark
#
import unittest
import time
import concurrent.bench.pi.pi_aprox as pi

class TestBenchmarkPI(unittest.TestCase):

    def setUp(self):
        self.iterations = 1

    def test_benchmark_pi(self):
        #for iteration in self.iterations:
        for iteration in range(0,self.iterations):
            self._benchmark_worker(100*(10**iteration))

    def _benchmark_worker(self, iterations):
        # Cython implementation
        start = time.time()
        cython_v = pi.approx_pi(iterations)
        end = time.time()
        cython_t = end-start

        # Pure implementation
        start = time.time()
        python_v = pi.approx_pi_pure(iterations)
        end = time.time()
        python_t = end-start

        #print("[%i] Cython: %f, Python: %f. Improvement over pure python: %f%%" % (iterations,cython_t,python_t,(python_t/cython_t)*100.0))

        self.assertTrue(cython_v == python_v)

if __name__ == '__main__':
    unittest.main()
