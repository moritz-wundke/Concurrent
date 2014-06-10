'''
Just a simple reley to run our environment admin script
'''
import sys
from concurrent.core.environment.envadmin import main

if __name__ == '__main__':
    main(sys.argv[1:])