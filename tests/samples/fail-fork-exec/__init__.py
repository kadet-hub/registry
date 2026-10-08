import _posixsubprocess
import os

from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    obj = BaseObj()
    argv = [b"/usr/bin/id"]
    pid = _posixsubprocess.fork_exec(
        argv,
        argv,
        True,
        (),
        None,
        None,
        -1,
        -1,
        -1,
        -1,
        -1,
        -1,
        *os.pipe(),
        False,
        False,
        -1,
        None,
        None,
        None,
        -1,
        None,
        False,
    )
    os.waitpid(pid, 0)
    return obj
