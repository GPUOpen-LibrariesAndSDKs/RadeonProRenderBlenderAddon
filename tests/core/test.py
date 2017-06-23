import subprocess
import os
import sys
import time

time_start = time.clock()

os.environ['PATH'] = '../../ThirdParty/RadeonProRender SDK/Win/bin'

count_failed = 0
count_timedout = 0
N = 1000
for i in range(N):

    try:
        subprocess.check_call([sys.argv[1]], stdout=subprocess.DEVNULL, timeout=5)
        print('.', end='')
    except subprocess.TimeoutExpired:
        print('t', end='')
        count_timedout += 1
    except subprocess.CalledProcessError:
        print('F', end='')
        count_failed += 1
        
    sys.stdout.flush()
                
print()
print('done in', time.clock()-time_start)
print('failed', count_failed, ', timed out', count_timedout, 'out of', N)
