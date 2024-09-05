#!/usr/bin/env python3
import unittest
import socket
import socketserver
import re
import os
import subprocess
import time
import tempfile
import sys
import py_compile
import pathlib

PYFLOW_PATH = pathlib.Path(__file__).parent.parent.resolve() / 'pyflow.py'

VERBOSE = True


def pprint(msg):
  if VERBOSE:
    print(msg, file=sys.stderr, flush=True)


SERVER_SCRIPT = b"""\
import socketserver
import hashlib
import time

FLAG = b'really_secure{Hello World}'

def current_time(): 
  return int(time.time())

def generate_key():
  ts = current_time()
  return hashlib.sha256(ts.to_bytes(4, 'big')).digest()

def encrypt(msg):
  key = generate_key()
  ct = b''
  for i in range(0, len(msg), len(key)):
    ct += bytes([b1 ^ b2 for b1, b2 in zip(msg[i:i+len(key)], key)])
  return ct

class TCPHandler(socketserver.BaseRequestHandler):
  def handle(self):
    self.data = self.request.recv(1024)
    print('%s:%r %r' % (self.client_address[0], self.client_address[1], self.data))
    if self.data == b'get_flag': response = encrypt(FLAG)
    else: response = encrypt(self.data)
    self.request.sendall(response)

def run_server(port):
  socketserver.TCPServer.allow_reuse_address = True
  with socketserver.TCPServer(('localhost', port), TCPHandler) as server:
    try:
      print(f'Listening on port {port}')
      server.serve_forever()
    except KeyboardInterrupt:
      server.shutdown()

if __name__ == '__main__':
  import argparse
  parser = argparse.ArgumentParser()
  parser.add_argument('-p', '--port', type=int, default=9000)
  args = parser.parse_args()
  run_server(args.port)
"""


class TestCommand(unittest.TestCase):
  @classmethod
  def setUpClass(self):
    # Create server.pyc
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.write(SERVER_SCRIPT)
    tmp.close()
    # target compiled file name
    cfile = str((pathlib.Path(__file__).parent / 'server.pyc').resolve())
    # purported file name (the file name that shows up in error messages and
    # function__entry and function__return probes)
    dfile = str((pathlib.Path(__file__).parent / 'server.py').resolve())
    py_compile.compile(tmp.name, cfile=cfile, dfile=dfile)
    pathlib.Path(tmp.name).unlink()
    self.server_pyc = cfile

    # Client script
    self.client_script = pathlib.Path(__file__).parent / 'client.py'

  # *** Common ***
  def run_trace(self, *, pyflow_args=None, server_args=None, client_args=None):
    if not os.fork():
      # run client script
      time.sleep(4)
      rc = subprocess.call(
        f'{sys.executable} {self.client_script} {client_args or ""}',
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
      )
      os._exit(rc)
    else:
      # run pyflow
      cmd = f"{sys.executable} {PYFLOW_PATH} {pyflow_args or ''} -c '{sys.executable} {self.server_pyc} {server_args or ''}'"
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
    out = self.run_trace(pyflow_args=None, server_args=None, client_args=None)
    patterns = [
      socket.__file__,
      socketserver.__file__,
    ]
    self.assertTrue(all(re.search(p, out) for p in patterns))

  def test_file_filter(self):
    filters = str(pathlib.Path('.').resolve())
    out = self.run_trace(
      pyflow_args=f'-f {filters}', server_args=None, client_args=None
    )
    patterns = [
      'tests/server.py',
    ]
    self.assertTrue(all(re.search(p, out) for p in patterns))

  def test_function_filter(self):
    filters = (
      'process_request finish_request encrypt generate_key current_time'
    )
    out = self.run_trace(
      pyflow_args=f'-F {filters}', server_args=None, client_args=None
    )
    patterns = [
      rf'.+\.py:({filters.replace(" ", "|")}):',
    ]
    self.assertTrue(all(re.search(p, out) for p in patterns))

  def test_multi_args(self):
    out = self.run_trace(
      pyflow_args=None, server_args='-p 9001', client_args='-p 9001'
    )
    patterns = [
      socket.__file__,
      socketserver.__file__,
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
