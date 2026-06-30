import signal
import subprocess
import sys
import time


processes: list[subprocess.Popen] = []


def stop_all(_signum=None, _frame=None):
    for process in processes:
        if process.poll() is None:
            process.terminate()
    deadline = time.time() + 10
    for process in processes:
        while process.poll() is None and time.time() < deadline:
            time.sleep(0.2)
        if process.poll() is None:
            process.kill()


signal.signal(signal.SIGTERM, stop_all)
signal.signal(signal.SIGINT, stop_all)

processes.append(
    subprocess.Popen(["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"], cwd="/app")
)
processes.append(subprocess.Popen(["nginx", "-g", "daemon off;"]))

exit_code = 0
try:
    while True:
        for process in processes:
            code = process.poll()
            if code is not None:
                exit_code = code
                stop_all()
                raise SystemExit(exit_code)
        time.sleep(1)
except SystemExit:
    raise
except BaseException:
    stop_all()
    raise
finally:
    sys.exit(exit_code)
