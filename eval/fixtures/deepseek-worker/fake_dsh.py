"""Offline DSH fixture. Never calls a provider or reads authentication."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

if sys.argv[1:] == ['--heartbeat']:
    Path('child.pid').write_text(str(os.getpid()))
    while True:
        with Path('heartbeat.txt').open('a') as stream:
            stream.write('tick\n')
        time.sleep(0.03)

if sys.argv[1:] != ['--profile', 'headless', '--json', '-']:
    raise SystemExit(2)

task = json.loads(sys.stdin.buffer.read().decode('utf-8'))
case = task['case']
Path('worker.pid').write_text(str(os.getpid()))
print(json.dumps({'type': 'session', 'id': 'fake-' + case}), flush=True)
if case == 'busy':
    print(json.dumps({'type': 'error', 'message': 'server is busy'}), flush=True)
    print('server is busy; PRIVATE_DIAGNOSTIC_SENTINEL', file=sys.stderr, flush=True)
    raise SystemExit(75)
if case == 'timeout':
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--heartbeat'])
    time.sleep(60)
else:
    operator = '-' if case == 'bad_implementation' else '+'
    Path('calc.py').write_text('def add(a, b):\n    return a ' + operator + ' b\n')
    print(json.dumps({'type': 'final', 'text': 'Implemented add; tests pass. Tiếng Việt ✓'}), flush=True)
