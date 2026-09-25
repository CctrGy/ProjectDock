"""Propiedad del árbol de procesos; Windows Job Object / sesión POSIX."""
import ctypes
import os
import signal


class ProcessTree:
    def __init__(self, process):
        self.process = process
        self.handle = None
        if os.name == "nt":
            from ctypes import wintypes as w
            class Basic(ctypes.Structure):
                _fields_ = [("ProcessTime", ctypes.c_int64), ("JobTime", ctypes.c_int64),
                            ("Flags", w.DWORD), ("Minimum", ctypes.c_size_t),
                            ("Maximum", ctypes.c_size_t), ("Active", w.DWORD),
                            ("Affinity", ctypes.c_size_t), ("Priority", w.DWORD),
                            ("Scheduling", w.DWORD)]
            class Counters(ctypes.Structure):
                _fields_ = [(name, ctypes.c_uint64) for name in
                            ["ReadOps", "WriteOps", "OtherOps", "ReadBytes", "WriteBytes", "OtherBytes"]]
            class Extended(ctypes.Structure):
                _fields_ = [("Basic", Basic), ("IO", Counters),
                            ("ProcessMemory", ctypes.c_size_t), ("JobMemory", ctypes.c_size_t),
                            ("PeakProcess", ctypes.c_size_t), ("PeakJob", ctypes.c_size_t)]
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
            kernel.CreateJobObjectW.restype = w.HANDLE
            kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
            kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
            kernel.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
            kernel.CloseHandle.argtypes = [w.HANDLE]
            handle = kernel.CreateJobObjectW(None, None)
            info = Extended()
            info.Basic.Flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if handle and kernel.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)) and kernel.AssignProcessToJobObject(handle, int(process._handle)):
                self.kernel, self.handle = kernel, handle
            elif handle:
                kernel.CloseHandle(handle)

    def terminate(self):
        if self.handle:
            self.kernel.TerminateJobObject(self.handle, 130)
        elif os.name != "nt":
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            from .engine import terminate_tree
            terminate_tree(self.process.pid)

    def close(self):
        self.terminate()
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
