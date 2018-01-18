import sys
import os
import time
import subprocess

time_start = time.time()

debugger = sys.argv[3]

if not debugger:
	subprocess.check_call([sys.argv[1], 
    		#'--factory-startup', 
    		'-noaudio', 
		"--window-geometry","200","600","1280","960",
    		'--python', 
		sys.argv[2]]) 
else:
	print("Debugger: %s" % debugger)
	print("Use the folowing: run -noaudio --window-geometry 200 600 1280 960 --python %s" % sys.argv[2])
	subprocess.check_call([debugger,sys.argv[1]])
                           
print('done in', time.time()-time_start)
