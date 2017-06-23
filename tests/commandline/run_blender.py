import sys
import os
import time
import subprocess

time_start = time.time()

subprocess.check_call([sys.argv[1], 
    #'--factory-startup', 
    '-noaudio', 
    '--python', sys.argv[2]]) 

print('done in', time.time()-time_start)