# -*- coding: utf-8 -*-
"""
Simple test case using the TaskManager and some sample computation
"""
import unittest
import time
from concurrent.core.async.task import Task
from concurrent.core.async.api import ITaskManager
from concurrent.core.environment.environment import Environment
from concurrent.core.components.component import ExtensionPoint
from concurrent.core.config.config import ConfigHandle
import random, traceback

# TODO: Move fake config and env into global test helper

class FakeConfigHandle(ConfigHandle):
    """
    Fake configuration class used for testing
    """
    def save(self):
        pass

class FakeEnvironment(Environment):
    """
    Fake environment for our test
    """

    def create(self, args=None):
        self.setup_config()

    def check(self):
        return True

    def conditional_create_env_dirs(self):
        pass

    def setup_log(self):
        from concurrent.core.logging.log import logger_factory
        self.log = logger_factory()

    def is_component_enabled(self, cls):
        print(cls.__module__)
        return cls.__module__.startswith('trac.') and \
               cls.__module__.find('.tests.') == -1

    def setup_config(self, use_defaults=False):
        self.config = FakeConfigHandle('')
        self.setup_log()

class TestTask(Task):
    """
    Just a simple test task
    """

    def __init__(self):
        Task.__init__(self, "TestTask")
        self.sleep_time = random.uniform(0.01, 0.05)

    def __call__(self):
        """
        Executer a task
        """
        #print("Sleeping %f seconds" %(self.sleep_time))
        time.sleep(self.sleep_time)
        #print("Task finished")
        return ("Task was sleaping for %f seconds"%self.sleep_time)

    def __str__(self):
        """
        Tasks string representation
        """
        return ("Task that sleeps sleeps %f seconds" %(self.sleep_time))

class TestTaskManager(unittest.TestCase):

    # Get the tasks managers that we have
    task_managers = ExtensionPoint(ITaskManager)

    def setUp(self):
        # TODO: Move setup and teardown into global test helper, so we can
        # reuse all component stuff
        
        # Setup the component manager for the test
        from concurrent.core.components.component import ComponentManager, ComponentMeta
        self.compmgr = ComponentManager()

        # Open the test environment
        self.env = FakeEnvironment('', True)

        # We use the first one!
        for manager in self.task_managers:
            self.task_manager = manager
            break;

        # Make sure we have no external components hanging around in the
        # component registry
        self.old_registry = ComponentMeta._registry
        ComponentMeta._registry = {}

    def tearDown(self):
        # Restore the original component registry
        from concurrent.core.components.component import ComponentMeta
        ComponentMeta._registry = self.old_registry

    def test_task_manager(self):
        try:
            self.task_manager.init();
            self.task_manager.start();

            # Add some taks
            for i in range(5):
                self.task_manager.put_task(TestTask())

            self.task_manager.stop();
        except Exception as e:
            traceback.print_exc()

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(unittest.TestLoader().loadTestsFromTestCase(TestTaskManager))
