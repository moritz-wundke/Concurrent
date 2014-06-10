# -*- coding: utf-8 -*-
"""
Just a very simple python file importing all modules one by one
"""
if __name__ == '__main__':
	# Import core
	from concurrent.core.application.api import *
	from concurrent.core.application.application import *

	from concurrent.core.async.api import *
	from concurrent.core.async.task import *

	from concurrent.core.components.baseobject import *
	from concurrent.core.components.component import *
	from concurrent.core.components.componentloader import *

	from concurrent.core.config.config import *

	from concurrent.core.db.api import *
	from concurrent.core.db.dbengines import *
	from concurrent.core.db.dbmanager import *

	from concurrent.core.environment.api import *
	from concurrent.core.environment.envadmin import *
	from concurrent.core.environment.environment import *

	from concurrent.core.exceptions.baseerror import *

	from concurrent.core.logging.log import *

	from concurrent.core.util.date import *
	from concurrent.core.util.filehandling import *
	from concurrent.core.util.texttransforms import *
	from concurrent.core.util.utils import *

	# Import tools

	from concurrent.tools.console import *

	# Now import framework
	from concurrent.framework.application.application import *

	import sys
	try:
	    from concurrent.bench.pi.pi_aprox import *
	except ImportError as err:
	    print("ERROR: Please build cython first [%s]" % err)
	    sys.exit(1)

	print("Imports has been performed success fully, seams that all is ready to go!")
	sys.exit(0)
