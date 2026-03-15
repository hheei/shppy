import os
import select
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Optional


class Shell:
    def __init__(self, executable: Optional[str] = None) -> None:
        self.executable = executable or os.environ.get('SHELL') or '/bin/sh'
        self.proc = subprocess.Popen(
            [self.executable],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
            env=os.environ.copy()
        )
        
        if self.proc.stdin is None or self.proc.stdout is None or self.proc.stderr is None:
            raise RuntimeError("Failed to initialize shell process with pipes.")

        self._stdin = self.proc.stdin
        self._stdout = self.proc.stdout
        self._stderr = self.proc.stderr
        
        self._code = 0
        self._out = []
        self._err = []
        self._generation = 0
        self._read_generation = -1
        
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._last_future = None
        self._state_lock = threading.Lock()
        
    def wait(self, timeout = None) -> "Shell":
        if self._last_future:
            try:
                self._last_future.result(timeout=timeout)
            except TimeoutError:
                pass
        return self

    def close(self) -> None:
        self._executor.shutdown(wait=False)
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None
    
    def run(self, command: str, timeout: float = -1) -> "Shell":
        with self._state_lock:
            if self._read_generation == self._generation:
                self._generation += 1
                self._code = 0
                self._out = []
                self._err = []
            current_gen = self._generation

        self._last_future = self._executor.submit(self._worker, command, timeout, current_gen)
        return self

    def _worker(self, command: str, timeout: float, generation: int) -> None:
        token = f"__SHELL_EXIT_{uuid.uuid4().hex}__"
        code = -1
        out_acc, err_acc = [], []
        
        try:
            if self.proc is None or self.proc.poll() is not None:
                err_acc.append("Shell process has been closed or died")
            else:
                self._stdin.write(f"{command}\nprintf '%s %s\\n' '{token}' $?\n")
                self._stdin.flush()

                stdout_fd = self._stdout.fileno()
                stderr_fd = self._stderr.fileno()
                active_fds = {stdout_fd, stderr_fd}
                start_time = time.time()

                while active_fds:
                    if timeout >= 0 and (time.time() - start_time) >= timeout:
                        err_acc.append("Command timed out")
                        break

                    readable, _, _ = select.select(active_fds, [], [], 0.5)
                    for fd in readable:
                        stream = self._stdout if fd == stdout_fd else self._stderr
                        line = stream.readline()
                        
                        if not line:
                            active_fds.discard(fd)
                            continue

                        if fd == stdout_fd:
                            if line.startswith(token):
                                code = int(line.split()[1])
                                active_fds.clear()
                            else:
                                out_acc.append(line.rstrip("\n"))
                        else:
                            err_acc.append(line.rstrip("\n"))

            with self._state_lock:
                if generation == self._generation:
                    self._code = code
                    self._out.extend(out_acc)
                    self._err.extend(err_acc)

        except Exception as exc:
            with self._state_lock:
                if generation == self._generation:
                    self._code = -1
                    self._err.append(str(exc))

    @property
    def code(self) -> int:
        self.wait()
        return self._code

    @property
    def out(self) -> str:
        self.wait()
        with self._state_lock:
            self._read_generation = self._generation
            return "\n".join(self._out)

    @property
    def err(self) -> str:
        self.wait()
        with self._state_lock:
            self._read_generation = self._generation
            return "\n".join(self._err)

    @property
    def ok(self) -> bool:
        self.wait()
        return self.code == 0

    def __repr__(self) -> str:
        if self._last_future is not None and not self._last_future.done():
            return "<Shell [Running]>"
            
        with self._state_lock:
            return f"<Shell [Exit {self._code}]>"

    def __enter__(self) -> "Shell":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
