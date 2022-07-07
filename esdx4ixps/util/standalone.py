import ctypes
import os
import signal
import subprocess
import time


def run_django():
    if os.path.exists("db.sqlite3"):
        os.remove("db.sqlite3")
    p = subprocess.Popen(["./manage.py", "migrate"], stdout=subprocess.DEVNULL)
    p.wait()
    p = subprocess.Popen(
        ["./manage.py", "loaddata", "./market/fixtures/testdata.yaml"],
        stdout=subprocess.DEVNULL)
    p.wait()

    # from https://stackoverflow.com/questions/19447603/how-to-kill-a-python-child-process-\
    # created-with-subprocess-check-output-when-t/19448096#19448096
    libc = ctypes.CDLL("libc.so.6")
    def set_pdeathsig(sig = signal.SIGTERM):
        def callable():
            return libc.prctl(1, sig)
        return callable
    p = subprocess.Popen(["./manage.py", "grpcrunserver"],
        preexec_fn=set_pdeathsig(signal.SIGTERM))
    time.sleep(1)
    return p
