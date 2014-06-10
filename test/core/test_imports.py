# -*- coding: utf-8 -*-
"""
Simple test case using the TaskManager and some sample computation
"""
import unittest

class TestImports(unittest.TestCase):
    
    def test_core_imports(self):
        import concurrent.core.application.api
        import concurrent.core.application.api
        import concurrent.core.application.application
        import concurrent.core.application.pickler
    
        import concurrent.core.async.api
        import concurrent.core.async.task
    
        import concurrent.core.components.baseobject
        import concurrent.core.components.component
        import concurrent.core.components.componentloader
    
        import concurrent.core.config.config
    
        import concurrent.core.db.api
        import concurrent.core.db.dbengines
        import concurrent.core.db.dbmanager
    
        import concurrent.core.environment.api
        import concurrent.core.environment.envadmin
        import concurrent.core.environment.environment
    
        import concurrent.core.exceptions.baseerror
    
        import concurrent.core.logging.log
    
        import concurrent.core.util.date
        import concurrent.core.util.filehandling
        import concurrent.core.util.texttransforms
        import concurrent.core.util.utils
    
    def test_tools_imports(self):
        import concurrent.tools.console
    
    def test_framework_imports(self):
        import concurrent.framework.nodes.basenodes
        import concurrent.framework.nodes.masternode
        import concurrent.framework.nodes.slavenode
        import concurrent.framework.nodes.clientnode
    
    def test_cycthon_imports(self):
        import sys
        try:
            import concurrent.bench.pi.pi_aprox
        except ImportError as err:
            print("ERROR: Please build cython first [%s]" % err)
            sys.exit(1)

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(unittest.TestLoader().loadTestsFromTestCase(TestImports))
