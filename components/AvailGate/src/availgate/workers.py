"""Killable spawned workers give network operations a real wall-clock budget."""

import multiprocessing as mp
import time
from collections import deque


def _entry(pipe, function, arguments):
    try:
        pipe.send({"value": function(*arguments)})
    except BaseException:
        # Raw exceptions may contain query strings or credentials.
        pipe.send({"failure": "worker_error"})
    finally:
        pipe.close()


def run_jobs(function, jobs, *, timeout=30, concurrency=4):
    """Return results in submission order. No child survives this call."""
    ctx = mp.get_context("spawn")
    pending = deque(enumerate(jobs))
    active = {}
    outcomes = [None] * len(jobs)
    deadline = time.monotonic() + timeout
    try:
        while (pending or active) and time.monotonic() < deadline:
            while pending and len(active) < concurrency:
                index, arguments = pending.popleft()
                reader, writer = ctx.Pipe(duplex=False)
                process = ctx.Process(target=_entry, args=(writer, function, arguments), daemon=True)
                process.start()
                writer.close()
                active[index] = (process, reader)
            for index, (process, pipe) in list(active.items()):
                if pipe.poll():
                    try:
                        outcomes[index] = pipe.recv()
                    except (EOFError, OSError):
                        outcomes[index] = {"failure": "worker_error"}
                elif not process.is_alive():
                    outcomes[index] = {"failure": "worker_error"}
                else:
                    continue
                pipe.close()
                process.join(timeout=0.01)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=0.1)
                if process.is_alive():
                    process.kill()
                    process.join()
                process.close()
                del active[index]
            if pending or active:
                time.sleep(min(0.01, max(0, deadline - time.monotonic())))
    finally:
        for process, pipe in active.values():
            if process.is_alive():
                process.terminate()
            process.join(timeout=0.1)
            if process.is_alive():
                process.kill()
                process.join()
            pipe.close()
            process.close()
    return [outcome if outcome is not None else {"failure": "timeout"} for outcome in outcomes]
