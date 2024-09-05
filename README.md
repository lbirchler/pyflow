# pyflow
---

BCC based tool to trace function call/return hierarchy of Python scripts and processes.

Initially created to debug packages that ship with PYC-only files.

## Requirements
- [BCC](https://github.com/iovisor/bcc/blob/master/INSTALL.md)

## Usage
```
usage: pyflow.py [-h] [-p PID] [-c CMD] [-f [FILES ...]] [-F [FUNCS ...]] [-t TMP_DIR] [-v]

Trace function call/return hierarchy of Python scripts and processes.

options:
  -h, --help            show this help message and exit
  -p PID, --pid PID     Process ID to trace.
  -c CMD, --cmd CMD     Command to execute and trace. Enclose in quotes if the command has multiple arguments.
  -f [FILES ...], --files [FILES ...]
                        Filename filters. Only trace functions in these files. Relative paths are allowed.
  -F [FUNCS ...], --funcs [FUNCS ...]
                        Function filters. Only trace these function calls.
  -t TMP_DIR, --tmp-dir TMP_DIR
                        Temporary script directory. Only used when tracing a command (--cmd).
  -v, --verbose         Verbose mode. Multiple -v options increase the verbosity. The maximum is 3.

examples:
  ./pyflow.py -p 1001                           Trace all files and functions in process 1001
  ./pyflow.py -f /usr/lib/python3.10/socket.py  Only trace functions in socket.py
  ./pyflow.py -F get_request accept daemon      Trace get_request, accept and daemon functions
  ./pyflow.py -c "python3 script.py"            Run script.py and trace all files and functions
```

## Examples

### Trace Process

Trace all files and functions in process 695285:
```
$ python3 -m http.server 9000 &> /dev/null &
[1] 695285
$ sudo ./pyflow.py -p 695285
Tracing function calls in process 695285... Ctrl-C to quit.
TIME            CPU PID     TID     FILE:FUNC:LINE
14:54:52.847071 7   695285  695285  <=  /usr/lib/python3.10/selectors.py:select:429
14:54:52.847452 7   695285  695285  =>  /usr/lib/python3.10/socketserver.py:service_actions:254
14:54:52.847629 7   695285  695285  <=  /usr/lib/python3.10/socketserver.py:service_actions:260
14:54:52.847780 7   695285  695285  =>  /usr/lib/python3.10/selectors.py:select:403
14:54:53.347216 7   695285  695285  <=  /usr/lib/python3.10/selectors.py:select:429
14:54:53.347467 7   695285  695285  =>  /usr/lib/python3.10/socketserver.py:service_actions:254
14:54:53.347705 7   695285  695285  <=  /usr/lib/python3.10/socketserver.py:service_actions:260
14:54:53.347942 7   695285  695285  =>  /usr/lib/python3.10/selectors.py:select:403
14:54:53.847788 7   695285  695285  <=  /usr/lib/python3.10/selectors.py:select:429
14:54:53.848038 7   695285  695285  =>  /usr/lib/python3.10/socketserver.py:service_actions:254
14:54:53.848291 7   695285  695285  <=  /usr/lib/python3.10/socketserver.py:service_actions:260
14:54:53.848531 7   695285  695285  =>  /usr/lib/python3.10/selectors.py:select:403
14:54:54.348438 7   695285  695285  <=  /usr/lib/python3.10/selectors.py:select:429
14:54:54.348701 7   695285  695285  =>  /usr/lib/python3.10/socketserver.py:service_actions:254
14:54:54.348927 7   695285  695285  <=  /usr/lib/python3.10/socketserver.py:service_actions:260
14:54:54.349155 7   695285  695285  =>  /usr/lib/python3.10/selectors.py:select:403
14:54:54.849104 7   695285  695285  <=  /usr/lib/python3.10/selectors.py:select:429
```

### Trace Command

Run `tests/script.py` and trace all files and functions:
```
$ sudo ./pyflow.py -c "python3 tests/script.py"
Tracing function calls in process 847740... Ctrl-C to quit.
TIME            CPU PID     TID     FILE:FUNC:LINE
13:47:49.674749 11  847740  847740  <=  tests/script.py:function_1:4
13:47:50.675832 11  847740  847740  <=  tests/script.py:function_2:5
13:47:50.676016 11  847740  847740  =>  tests/script.py:function_3:6
13:47:50.676141 11  847740  847740    =>  tests/script.py:function_1:4
13:47:51.676644 11  847740  847740    <=  tests/script.py:function_1:4
13:47:51.676779 11  847740  847740    =>  tests/script.py:function_2:5
13:47:51.676892 11  847740  847740      =>  tests/script.py:function_1:4
13:47:52.677831 11  847740  847740      <=  tests/script.py:function_1:4
13:47:53.678781 11  847740  847740    <=  tests/script.py:function_2:5
13:47:54.679947 11  847740  847740  <=  tests/script.py:function_3:6
13:47:54.680116 11  847740  847740  <=  tests/script.py:main:8
13:47:54.680230 11  847740  847740  <=  tests/script.py:<module>:11
```

Run `tests/server.pyc` and trace all files and functions:
```
$ sudo ./pyflow.py -c "python3 tests/server.pyc"
Tracing function calls in process 696116... Ctrl-C to quit.
TIME            CPU PID     TID     FILE:FUNC:LINE
14:59:10.842217 8   696116  696116    <=  /usr/lib/python3.10/socketserver.py:get_request:499
14:59:10.842499 8   696116  696116    =>  /usr/lib/python3.10/socketserver.py:verify_request:333
14:59:10.842762 8   696116  696116    <=  /usr/lib/python3.10/socketserver.py:verify_request:339
14:59:10.843026 8   696116  696116    =>  /usr/lib/python3.10/socketserver.py:process_request:341
14:59:10.843304 8   696116  696116      =>  /usr/lib/python3.10/socketserver.py:finish_request:358
14:59:10.843573 8   696116  696116        =>  /usr/lib/python3.10/socketserver.py:__init__:741
14:59:10.843854 8   696116  696116          =>  /usr/lib/python3.10/socketserver.py:setup:751
14:59:10.844119 8   696116  696116          <=  /usr/lib/python3.10/socketserver.py:setup:752
14:59:10.844276 8   696116  696116          =>  tests/server.py:handle:22
14:59:10.844415 8   696116  696116            =>  tests/server.py:encrypt:14
14:59:10.844549 8   696116  696116              =>  tests/server.py:generate_key:10
14:59:10.844684 8   696116  696116                =>  tests/server.py:current_time:7
14:59:10.844819 8   696116  696116                <=  tests/server.py:current_time:8
14:59:10.844941 8   696116  696116              <=  tests/server.py:generate_key:12
```

### Filters

Tracing a script or process without any filters will produce a lot of output. Multiple filename and/or function filters can be provided to limit the amount of output.

Only trace functions in `socket.py` and `threading.py` in process 696517:
```
$ sudo ./pyflow.py -p 696517 -f /usr/lib/python3.10/socket.py /usr/lib/python3.10/threading.py
Tracing function calls in process 696517... Ctrl-C to quit.
TIME            CPU PID     TID     FILE:FUNC:LINE
15:03:07.945656 4   696517  696517  =>  /usr/lib/python3.10/socket.py:accept:286
15:03:07.945910 4   696517  696517    =>  /usr/lib/python3.10/socket.py:family:514
15:03:07.946066 4   696517  696517      =>  /usr/lib/python3.10/socket.py:_intenum_converter:99
15:03:07.946216 4   696517  696517      <=  /usr/lib/python3.10/socket.py:_intenum_converter:105
15:03:07.946414 4   696517  696517    <=  /usr/lib/python3.10/socket.py:family:518
15:03:07.946565 4   696517  696517    =>  /usr/lib/python3.10/socket.py:type:520
15:03:07.946712 4   696517  696517      =>  /usr/lib/python3.10/socket.py:_intenum_converter:99
15:03:07.946857 4   696517  696517      <=  /usr/lib/python3.10/socket.py:_intenum_converter:105
15:03:07.947002 4   696517  696517    <=  /usr/lib/python3.10/socket.py:type:524
15:03:07.947157 4   696517  696517    =>  /usr/lib/python3.10/socket.py:__init__:220
15:03:07.947303 4   696517  696517    <=  /usr/lib/python3.10/socket.py:__init__:234
15:03:07.947441 4   696517  696517  <=  /usr/lib/python3.10/socket.py:accept:300
15:03:07.947544 4   696517  696517  =>  /usr/lib/python3.10/threading.py:__init__:827
15:03:07.947638 4   696517  696517    =>  /usr/lib/python3.10/threading.py:_newname:782
```

Only trace `accept`, `get_request`, and `daemon` calls in process 696517:
```
$ sudo ./pyflow.py -p 696517 -F accept get_request daemon
Tracing function calls in process 696517... Ctrl-C to quit.
TIME            CPU PID     TID     FILE:FUNC:LINE
15:05:12.087987 4   696517  696517  =>  /usr/lib/python3.10/socketserver.py:get_request:493
15:05:12.088274 4   696517  696517    =>  /usr/lib/python3.10/socket.py:accept:286
15:05:12.088441 4   696517  696517    <=  /usr/lib/python3.10/socket.py:accept:300
15:05:12.088599 4   696517  696517  <=  /usr/lib/python3.10/socketserver.py:get_request:499
15:05:12.088754 4   696517  696517  =>  /usr/lib/python3.10/threading.py:daemon:1183
15:05:12.088906 4   696517  696517  <=  /usr/lib/python3.10/threading.py:daemon:1196
15:05:12.089055 4   696517  696517  =>  /usr/lib/python3.10/threading.py:daemon:1198
15:05:12.089204 4   696517  696517  <=  /usr/lib/python3.10/threading.py:daemon:1204
15:05:12.089352 4   696517  696517  =>  /usr/lib/python3.10/threading.py:daemon:1183
15:05:12.089500 4   696517  696517  <=  /usr/lib/python3.10/threading.py:daemon:1196
15:05:12.089824 2   696517  696903  =>  /usr/lib/python3.10/threading.py:daemon:1183
15:05:12.089984 2   696517  696903  <=  /usr/lib/python3.10/threading.py:daemon:1196
15:05:14.536164 5   696517  696517  =>  /usr/lib/python3.10/socketserver.py:get_request:493
15:05:14.536485 5   696517  696517    =>  /usr/lib/python3.10/socket.py:accept:286
```

**Resources**
- [Instrumenting CPython with DTrace and SystemTap](https://docs.python.org/3/howto/instrumentation.html)
