#!/usr/bin/env python3
"""Bounded local vLLM capture RPC for subprocess-driven backend polling."""
import sys
import urllib.request

if __name__ == '__main__':
    request = urllib.request.Request(sys.argv[1], data=b'', method='POST')
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f'Capture RPC returned {response.status}')
        response.read()
