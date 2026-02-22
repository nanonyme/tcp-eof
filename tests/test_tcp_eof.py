#!/usr/bin/env python3
"""Test that the tcp-eof service accepts connections and closes them with EOF."""

import socket
import sys
import time


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <port>", file=sys.stderr)
        sys.exit(1)

    port = int(sys.argv[1])

    for attempt in range(10):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect(("127.0.0.1", port))
            data = s.recv(1024)
            if data == b"":
                print("OK: Connection accepted and closed with EOF")
                sys.exit(0)
            else:
                print("FAIL: Got unexpected data:", repr(data))
                sys.exit(1)
        except ConnectionRefusedError:
            if attempt < 9:
                time.sleep(1)
            else:
                print("FAIL: Container did not become ready in time")
                sys.exit(1)


if __name__ == "__main__":
    main()
