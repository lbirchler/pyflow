#!/usr/bin/env python3
import socket
import re
import hashlib
import time


def generate_key_for_ts(ts):
  key = ts.to_bytes(4, 'big')
  return hashlib.sha256(key).digest()


def decrypt(ct, ts):
  key = generate_key_for_ts(ts)
  pt = b''
  for i in range(len(ct)):
    pt += bytes([ct[i] ^ key[i]])
  return pt


def crack(ct: bytes):
  current_time = int(time.time())
  for offset in range(-100, 101):
    ts = current_time + offset
    try:
      decrypted_flag = decrypt(ct, ts)
      if re.search(rb'.+{.+}', decrypted_flag):
        print(f'Timestamp: {ts} Decrypted flag: {decrypted_flag.decode()}')
        break
    except Exception as e:
      pass


def send_msg(ip, port, msg):
  try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
      sock.connect((ip, port))
      sock.sendall(msg)
      response = sock.recv(1024)
      print('< %r\n> %r' % (msg, response))
      return response
  except Exception as e:
    print(f'Error sending message to {ip}:{port}: {e}')


if __name__ == '__main__':
  import argparse

  parser = argparse.ArgumentParser()
  parser.add_argument('-p', '--port', type=int, default=9000)
  args = parser.parse_args()
  encrypted_flag = send_msg('localhost', args.port, b'get_flag')
  crack(encrypted_flag)
  send_msg('localhost', args.port, b'lol')
