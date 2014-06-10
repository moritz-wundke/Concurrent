"""
Script that invokes all benchmark test cases within the test folder
"""
import unittest
import os
import sys

PATH_SEP = ("%s"%os.sep)

def find_test_files():
    """
    Find all files that are meant to contain benchmark test cases
    """
    for root, _, files in os.walk('test'):
        for filename in files:
            filename_lower = filename.lower()
            if filename_lower.startswith("bench_") and \
                filename_lower.endswith(".py"):
                # Create module string instead of path
                path = os.path.join(root, filename)
                module = path[:-3]
                if module.startswith(".%s"%PATH_SEP):
                    module = module[2:]
                yield module.replace(PATH_SEP,".")

def create_test_suite():
    """
    Create test suits
    """
    modules = [x for x in find_test_files()]
    suites = [unittest.defaultTestLoader.loadTestsFromName(name) \
              for name in modules]
    return unittest.TestSuite(suites)

if __name__ == '__main__':
    # Create and run all tests
    unittest.TextTestRunner(verbosity=2).run(create_test_suite())
    print("Done")
    sys.exit(0)
