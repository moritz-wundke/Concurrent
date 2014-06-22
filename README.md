# Overview #
Concurrent aims to be a different type of task distribution system compared to what MPI like system do. It adds a simple but powerful application abstraction layer to distribute the logic of an entire application onto a swarm of clusters holding similarities with volunteer computing systems.

Traditional task distributed systems will just perform simple tasks onto the distributed system and wait for results. Concurrent goes one step further by letting the tasks and the application decide what to do. The programming paradigm is then totally async without any waits for results and based on notifications once a computation has been performed.

# Slides #

For a quick introduction about the framework have a peek onto the [project slides](http://moritz-wundke.github.io//Concurrent/slides/) covering most of the framework current state and future.

# API #

Concurrent comes with a simple and extendable API, the component system makes it easy to create new schedule strategies and managers. Nearly all functionality is plugable to tweak and adapt the framework for your needs.

For more information about the inner grains refer to the [API documentation](http://moritz-wundke.github.io//Concurrent/API/).

# Usage #

To show how to use Concurrent for your own tasks we will create a simple _hello world_ application that just computes the string on the system and returns it to our application.

For this example we will create two classes, one which actually gets executed on the distributed system `class SimpleTask(Task):` and our application which interacts with the system and controls the task flow `class SimpleConcurrentApp(ApplicationNode)`. Our task class just gets executed on an arbitrary processes within the system while our application is what is getting executed on the client side creating the task, sending it to the framework and waiting for its completion.

The application itself is executed from a sandbox like environment enabling us to configure its behavior and monitor the application easily.

```python
from concurrent.framework.nodes.applicationnode import ApplicationNode
from concurrent.core.application.api import IApp
from concurrent.core.components.component import implements
from concurrent.core.async.task import Task

class SimpleTask(Task):
    def __init__(self, name, client_id):
        """
        Just create a task specifying only a client_id, this
        will tell Concurrent to only process the task and
        send the results back
        """
        Task.__init__(self, name, None, client_id)

    def __call__(self):
        """
        Method gets called on an arbitrary slave to perform
        the computation
        """
        return "Hello World"

    def finished(self, result, error):
        """
        Once the task is finished. Called on the MasterNode
        within the main thread once the node has recovered
        the result data.
        """
        print("Hey I'm done!")

class SimpleConcurrentApp(ApplicationNode):
    """
    Just a simple application showing how to send tasks to
    be processed using Concurrent
    """
    implements(IApp)

    def get_task_system(self):
        """
        Called from the base class when we are connected 
        to a MasterNode and we are able to send computation 
        tasks over
        """
        # We return none for the simple example, to check 
        # more advanced samples please check the samples 
        # source code
        return None

    def start_processing(self):
        """
        Called when the app is not using a ITaskSystem and
        will instead just add tasks and will take care of
        the task flow itself
        """
        self.log.info("Starting computation")

        # Create a task and send it to the system
        self.push_task(
            SimpleTask("my_task",self.node_id_str) )

    def task_finished(self, task, result, error):
        """
        Called when a task has been done
        """
        self.log.info(result)

        # shutdown
        self.shutdown_main_loop()

    def push_task_response(self, result):
        """
        We just add a Task to the computation framework
        """
        self.log.info("Task send to computation " \
            "framework")
    
    def push_task_failed(self, result):
        """
        We failed to add a Task to the computation
        framework
        """
        self.log.info("Failed to send task send to " \
            "computation framework")
    
    def push_tasks_response(self, result):
        """
        We just add a set of Tasks to the computation
        framework
        """
        self.log.info("Tasks send to computation " \ 
            "framework")
    
    def push_tasks_failed(self, result):
        """
        We failed to add a set of Tasks to the computation
        framework
        """
        self.log.info("Failed to send tasks send to " \
            "computation framework")
```

# Install #
The easiest way to install concurrent is to download it's source package and just install it using pythons disctools:

    python setup.py build_ext
    python setup.py install

Make sure to have the python development headers installed, you also require a valid C compiler.

# Releases #

The project is still in its alpha state and so use in production is still not recommended. The project follows the [GitFlow](http://nvie.com/posts/a-successful-git-branching-model/) branching pattern.

## Alpha 0.1.1 ##

First alpha release, samples are working and the system is reasonably stable.

### Features ###

 * ZeroMQ compute channel (no plain TCP sockets, while they are still in there)
 * Sending work and polling work patterns
 * Statistics system for all sybsystems
 * Sandbox environments
 * JSON-RPC API and web interface
 * Fault tolerance (client is notified on error)

## develop ##

The develop branch features the most recent and unstable work. It may not even compile. 

## master ##

The master branch is pointing always to the most stable release, in our case this is Alpha 0.1.1

# License #

MIT
