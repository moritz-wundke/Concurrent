import unittest
import time
import hashlib
import os
import multiprocessing

# Base concurrent path
TOPDIR = os.path.join("..","..","..")

class TestBenchmarkPool(unittest.TestCase):

    def setUp(self):
        pass

    def compute_digest(self, filename):
        digest = hashlib.sha512()
        f = open(filename,'rb')
        while True:
            chunk = f.read(8192)
            if not chunk: break
            digest.update(chunk)
        f.close()
        return digest.digest()


    def sequential(self):
        """A sequential function that walks a directory and computes
        SHA-512 hashes for all files"""
        start = time.time()
        digest_map = {}
        for path, dirs, files in os.walk(TOPDIR):
            for name in files:
                fullname = os.path.join(path,name)
                if os.path.exists(fullname):
                    digest_map[fullname] = self.compute_digest(fullname)
        end = time.time()
        #print ("Sequential:",end-start,"seconds")
        return digest_map

    def parallel(self):
        """A function that does the same calculation using pools"""
        start = time.time()
        p = multiprocessing.Pool(2)     # Make a process pool
        digest_map = {}
        for path, dirs, files in os.walk(TOPDIR):
            for name in files:
                fullname = os.path.join(path,name)
                if os.path.exists(fullname):
                    digest_map[fullname] = p.apply_async(
                        self.compute_digest, (fullname,)
                        )

        # Go through the final dictionary and collect results
        for filename, result in digest_map.items():
            digest_map[filename] = result.get()
        end = time.time()
        #print ("Process pool:",end-start,"seconds")
        return digest_map
    # aaa
    def test_benchmark_pool(self):
        """"""
        map1 = self.sequential()
        map2 = self.parallel()

        self.assertTrue(map1 == map2)


if __name__ == '__main__':
    unittest.main()
