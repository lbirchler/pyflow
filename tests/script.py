#!/usr/bin/env python3
import time


def function_1():
  time.sleep(1)


def function_2():
  function_1()
  time.sleep(1)


def function_3():
  function_1()
  function_2()
  time.sleep(1)


def main():
  function_1()
  function_2()
  function_3()


if __name__ == '__main__':
  main()
