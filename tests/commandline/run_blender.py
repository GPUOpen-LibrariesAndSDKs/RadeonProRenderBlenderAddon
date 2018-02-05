import sys
import os
import time
import subprocess

time_start = time.time()

debugger = None
# Only the OSX run script sets the debugger from the command
# line currently
if len(sys.argv) >= 4:
	debugger = sys.argv[3]

if not debugger:
	subprocess.check_call([sys.argv[1], 
    		#'--factory-startup', 
    		'-noaudio', 
		"--window-geometry","200","600","1920","1080",
    		'--python', 
		sys.argv[2]]) 
else:
	print("Debugger: %s" % debugger)
	subprocess.check_call([debugger,sys.argv[1],
		'--', 
    		#'--factory-startup', 
    		'-noaudio', 
		"--window-geometry","200","600","1920","1080",
    		'--python', 
		sys.argv[2]])
                           
print('done in', time.time()-time_start)
