#!/usr/bin/env python3
import unittest
import re
import os
import subprocess
import time
import socket
import socketserver
import threading
import sys
import pathlib

PYFLOW_PATH = pathlib.Path(__file__).parent.parent.resolve() / 'pyflow.py'

VERBOSE = True


def pprint(msg):
  if VERBOSE:
    print(msg, file=sys.stderr, flush=True)


class TestProcess(unittest.TestCase):
  @classmethod
  def setUpClass(self):
    # Start server
    self.server_proc = subprocess.Popen(
      [
        sys.executable,
        '-m',
        'http.server',
        '9000',
        '-d',
        str(PYFLOW_PATH.parent),
      ],
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
    )
    self.server_pid = self.server_proc.pid
    pprint(f'Server PID {self.server_pid}')

  @classmethod
  def tearDownClass(self):
    self.server_proc.kill()

  # *** Common ***
  def run_trace(self, *, pyflow_args=None):
    if not os.fork():
      # get file
      time.sleep(2)
      rc = subprocess.call(
        'curl localhost:9000/pyflow.py',
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
      )
      os._exit(rc)
    else:
      # run pyflow
      cmd = f'{PYFLOW_PATH} {pyflow_args}'
      p = subprocess.run(
        f'sudo bash -c "timeout 5 {cmd}"',
        shell=True,
        capture_output=True,
        text=True,
      )
      pprint(cmd)
      pprint(p.stdout)
      pprint(p.stderr)
      os.wait()
      return p.stdout

  # *** Tests ***
  def test_trace_all(self):
    out = self.run_trace(pyflow_args=f'-p {self.server_pid}')
    patterns = [socket.__file__, socketserver.__file__, threading.__file__]
    self.assertTrue(all(re.search(p, out) for p in patterns))

  def test_file_filter(self):
    filters = socket.__file__
    out = self.run_trace(pyflow_args=f'-f {filters} -p {self.server_pid}')
    patterns = socket.__file__
    self.assertTrue(all(re.search(p, out) for p in patterns))

  def test_function_filter(self):
    filters = 'accept get_request daemon'
    out = self.run_trace(pyflow_args=f'-F {filters} -p {self.server_pid}')
    patterns = [
      rf'.+\.py:({filters.replace(" ", "|")}):',
    ]
    self.assertTrue(all(re.search(p, out) for p in patterns))


if __name__ == '__main__':
  import argparse

  parser = argparse.ArgumentParser()
  parser.add_argument(
    '-v', '--verbose', action='count', default=0, help='max=3'
  )
  args, remaining = parser.parse_known_args()
  VERBOSE = args.verbose >= 3
  remaining.insert(0, sys.argv[0])
  unittest.main(argv=remaining, verbosity=min(args.verbose, 2))
