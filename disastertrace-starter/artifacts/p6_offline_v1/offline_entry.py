"""Run one offline CLI with outbound sockets denied, independent of available credentials."""

import os
import runpy
import sys


def guard(event, args):
    if event == "socket.connect":
        raise RuntimeError("P6 offline phase forbids network access")


os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
sys.addaudithook(guard)
module = sys.argv[1]
if module not in ("disastertrace.post_p5.cli", "disastertrace.repeat_eval.cli"):
    raise ValueError("unsupported offline module")
sys.argv = sys.argv[1:]
runpy.run_module(module, run_name="__main__")
