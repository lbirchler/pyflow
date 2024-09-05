#!/usr/bin/env python3
import argparse
import contextlib
import ctypes
import datetime
import os
import pathlib
import shlex
import shutil
import signal
import sys
import tempfile
import time

from bcc import BPF, USDT

VERBOSE = False
BPF_DEBUG = False
START_TS = time.time()
MAX_FILTER_LEN = 64  # max filename and function str length


def pprint(msg):
  if VERBOSE:
    print(f'[{time.time() - START_TS:09.3f}] {msg}', file=sys.stderr)
    sys.stderr.flush()


PROG_TEMPLATE = """
#define MAX_LEN @@MAX_LEN

struct event_t {
    u64 depth; /* first bit is direction (0 entry, 1 return) */
    u64 pid;
    u32 lineno;
    char filename[MAX_LEN];
    char function[MAX_LEN];
};

BPF_PERF_OUTPUT(events);
BPF_HASH(entry, u64, u64);

/* This can be written a handful of ways. Slight changes can lead to BPF verifier
 * errors. The following has been the most reliable in testing. */
static inline int strncmp(const char *str1, const char *str2, int size)
{
    int len = 0;
    unsigned char c1, c2;
    while (len++ < size) {
        c1 = *str1++;
        c2 = *str2++;
        if (c1 != c2) return 1; 
        if (!c1) break;
    }
    return 0;
}

int python_entry(struct pt_regs *ctx) {
    u64 *depth, zero = 0, filename = 0, function = 0;
    struct event_t data = {};

    bpf_usdt_readarg(1, ctx, &filename);
    bpf_usdt_readarg(2, ctx, &function);
    bpf_usdt_readarg(3, ctx, &data.lineno);
    bpf_probe_read_user(&data.filename, sizeof(data.filename), (void *)filename);
    bpf_probe_read_user(&data.function, sizeof(data.function), (void *)function);

    @@FILENAME_FILTER
    @@FUNCNAME_FILTER

    data.pid = bpf_get_current_pid_tgid();
    depth = entry.lookup_or_try_init(&data.pid, &zero);
    if (!depth) depth = &zero;
    data.depth = *depth + 1;
    ++(*depth);

    events.perf_submit(ctx, &data, sizeof(data));

    return 0;
}

int python_return(struct pt_regs *ctx) {
    u64 *depth, zero = 0, filename = 0, function = 0;
    struct event_t data = {};

    bpf_usdt_readarg(1, ctx, &filename);
    bpf_usdt_readarg(2, ctx, &function);
    bpf_usdt_readarg(3, ctx, &data.lineno);
    bpf_probe_read_user(&data.filename, sizeof(data.filename), (void *)filename);
    bpf_probe_read_user(&data.function, sizeof(data.function), (void *)function);

    @@FILENAME_FILTER
    @@FUNCNAME_FILTER

    data.pid = bpf_get_current_pid_tgid();
    depth = entry.lookup_or_try_init(&data.pid, &zero);
    if (!depth) depth = &zero;
    data.depth = *depth | (1ULL << 63);
    if (*depth) --(*depth);

    events.perf_submit(ctx, &data, sizeof(data));

    return 0;
}
"""


class event_t(ctypes.Structure):
  _fields_ = [
    ('depth', ctypes.c_ulonglong),
    ('pid', ctypes.c_ulonglong),
    ('lineno', ctypes.c_uint32),
    ('filename', ctypes.c_char * MAX_FILTER_LEN),
    ('function', ctypes.c_char * MAX_FILTER_LEN),
  ]


def gen_script(argv, dir=None):
  """Create a temporary executable script."""
  content = f"""#!/bin/env {sys.executable}\nimport os\nos.execve({argv[0]!r}, {argv!r}, os.environ)\n"""
  try:
    script_file = tempfile.NamedTemporaryFile(
      delete=False, dir=dir, suffix='.pyflow'
    )
    script_file.write(content.encode())
    script_file.flush()
    pathlib.Path(script_file.name).chmod(0o700)
    pprint(f'Created "{script_file.name}"\n{content}')
    return script_file.name
  except Exception as e:
    print(f'Error creating script file: {e}', file=sys.stderr)
    return None


def gen_bpf_prog(filenames=None, functions=None):
  """Generate a BPF program with optional filename and function filters."""

  def _build_filter(cmps):
    return f'if ({" && ".join(cmps)}) {{ return 0; }}' if cmps else ''

  filename_filter = _build_filter(
    [
      f'strncmp(data.filename, "{file}", {len(file)}) != 0'
      for file in filenames or []
    ]
  )
  function_filter = _build_filter(
    [
      f'strncmp(data.function, "{func}", {len(func)}) != 0'
      for func in functions or []
    ]
  )
  bpf_prog = (
    PROG_TEMPLATE.replace('@@MAX_LEN', str(MAX_FILTER_LEN))
    .replace('@@FILENAME_FILTER', filename_filter)
    .replace('@@FUNCNAME_FILTER', function_filter)
  )
  pprint(f'Generated BPF Program:\n{bpf_prog}')
  return bpf_prog


def print_event_header(pid):
  print(f'Tracing function calls in process {pid}... Ctrl-C to quit.')
  print(f'{"TIME":<15} {"CPU":<3} {"PID":<7} {"TID":<7} {"FILE:FUNC:LINE"}')


def print_event(cpu, data, size):
  """Perf buffer callback."""
  event = ctypes.cast(data, ctypes.POINTER(event_t)).contents
  depth = event.depth & (~(1 << 63))
  direction = '<= ' if event.depth & (1 << 63) else '=> '
  # print relative path if possible
  try:
    filename = str(
      pathlib.Path(event.filename.decode('utf-8', 'replace')).relative_to(
        pathlib.Path().cwd()
      )
    )
  except ValueError:
    filename = str(
      pathlib.Path(event.filename.decode('utf-8', 'replace')).resolve()
    )
  function = event.function.decode('utf-8', 'replace')
  lineno = event.lineno
  print(
    f'{datetime.datetime.now().strftime("%H:%M:%S.%f"):<15} '
    f'{cpu:<3} {event.pid >> 32:<7} {event.pid & 0xFFFFFFFF:<7} '
    f'{"  " * (depth - 1)}{direction} {filename}:{function}:{lineno}'
  )
  sys.stdout.flush()


@contextlib.contextmanager
def redirect_stream(stream=sys.stdout, file=os.devnull):
  """Temporarily redirect stream to file."""
  try:
    fd = open(file, 'w+', encoding='utf-8')
    saved = os.dup(stream.fileno())
    os.dup2(fd.fileno(), stream.fileno())
    yield
  finally:
    os.dup2(saved, stream.fileno())
    os.close(saved)
    fd.close()


def run_bpf_prog(prog, pid):
  """Enable USDT probes and run BPF program."""
  try:
    u = USDT(pid)
    u.enable_probe_or_bail('function__entry', 'python_entry')
    u.enable_probe_or_bail('function__return', 'python_return')
    b = BPF(text=prog, usdt_contexts=[u], debug=4 if BPF_DEBUG else 0)
    b['events'].open_perf_buffer(print_event)
    print_event_header(pid)
    while True:
      # ignore "Possibly lost N samples" output
      with redirect_stream(sys.stderr):
        b.perf_buffer_poll()
  except Exception as e:
    print(f'Error running BPF program: {e}', file=sys.stderr)


def trace_process(pid, bpf_prog):
  try:
    bpf_pid = os.fork()
    if bpf_pid == 0:
      run_bpf_prog(prog=bpf_prog, pid=pid)
    else:
      while pathlib.Path(f'/proc/{pid}').exists():
        time.sleep(1)
      os.kill(bpf_pid, signal.SIGKILL)
  except Exception as e:
    print(f'Error tracing process: {e}', file=sys.stderr)


def trace_command(cmd, dir, bpf_prog):
  script = gen_script(cmd, dir)
  if script is None:
    return
  try:
    r, w = os.pipe()
    cmd_pid = os.fork()
    if cmd_pid == 0:  # child
      os.close(w)
      nullfd = os.open(os.devnull, os.O_WRONLY)
      os.dup2(nullfd, 1)
      os.dup2(nullfd, 2)
      os.read(r, 1)  # wait for parent's kick
      os.execve(script, [script], os.environ)
    else:  # parent
      os.close(r)
      os.write(w, b'0')  # kick child
      os.close(w)
      time.sleep(0.5)
      bpf_pid = os.fork()
      if bpf_pid == 0:
        run_bpf_prog(prog=bpf_prog, pid=cmd_pid)
      else:
        os.waitpid(cmd_pid, 0)
        os.kill(bpf_pid, signal.SIGKILL)
  except Exception as e:
    print(f'Error tracing command: {e}', file=sys.stderr)
  finally:
    try:
      pathlib.Path(script).unlink()
      pprint(f'Deleted "{script}"')
    except FileNotFoundError:
      pass


# Arguments
def pid_arg(arg):
  """Check if /proc/PID exists and convert to int."""
  path = pathlib.Path(f'/proc/{arg}')
  if not path.exists():
    raise argparse.ArgumentTypeError(f'{arg}: Does not exist')
  return int(arg)


def cmd_arg(arg):
  """Convert to argv list and verify argv[0] is an executable file."""
  argv = shlex.split(arg)
  argv[0] = shutil.which(argv[0])
  if not os.access(argv[0], os.X_OK):
    raise argparse.ArgumentTypeError(f'{argv[0]}: Not an executable file.')
  return argv


def files_arg(arg):
  """Resolve path and verify less than MAX_FILTER_LEN."""
  path = str(pathlib.Path(arg).resolve())
  if len(path) > MAX_FILTER_LEN:
    raise argparse.ArgumentTypeError(f'{path}: Too long')
  return path


def funcs_arg(arg):
  """Verify less than MAX_FILTER_LEN."""
  if len(arg) > MAX_FILTER_LEN:
    raise argparse.ArgumentTypeError(f'{arg}: Too long')
  return arg


def parse_args():
  global VERBOSE, BPF_DEBUG

  parser = argparse.ArgumentParser(
    description='Trace function call/return hierarchy of Python scripts and processes.',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""\
examples:
  ./pyflow.py -p 1001                           Trace all files and functions in process 1001
  ./pyflow.py -f /usr/lib/python3.10/socket.py  Only trace functions in socket.py
  ./pyflow.py -F get_request accept daemon      Trace get_request, accept and daemon functions
  ./pyflow.py -c "python3 script.py"            Run script.py and trace all files and functions
  """,
  )
  parser.add_argument('-p', '--pid', type=pid_arg, help='Process ID to trace.')
  parser.add_argument(
    '-c',
    '--cmd',
    type=cmd_arg,
    help='Command to execute and trace. Enclose in quotes if the command has multiple arguments.',
  )
  parser.add_argument(
    '-f',
    '--files',
    nargs='*',
    type=files_arg,
    help='Filename filters. Only trace functions in these files. Relative paths are allowed.',
  )
  parser.add_argument(
    '-F',
    '--funcs',
    nargs='*',
    type=funcs_arg,
    help='Function filters. Only trace these function calls.',
  )
  parser.add_argument(
    '-t',
    '--tmp-dir',
    help='Temporary script directory. Only used when tracing a command (--cmd).',
  )
  parser.add_argument(
    '-v',
    '--verbose',
    action='count',
    default=0,
    help='Verbose mode. Multiple -v options increase the verbosity. The maximum is 3.',
  )

  args = parser.parse_args()

  if (args.pid and args.cmd) or (not args.pid and not args.cmd):
    parser.error('Either a PID (--pid) or a command (--cmd) must be provided.')

  VERBOSE = args.verbose >= 1
  BPF_DEBUG = args.verbose >= 2

  return args


def main():
  args = parse_args()

  bpf_prog = gen_bpf_prog(args.files, args.funcs)

  if args.pid:
    trace_process(args.pid, bpf_prog)
  if args.cmd:
    trace_command(args.cmd, args.tmp_dir, bpf_prog)


if __name__ == '__main__':
  with contextlib.suppress(KeyboardInterrupt):
    main()
