"""Block external network in the reproducibility subprocesses, allow loopback fixtures."""

import ipaddress
import os
import socket

if os.environ.get("DISASTERTRACE_OFFLINE") == "1":
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_lookup = socket.getaddrinfo

    def allowed(host):
        if host in ("localhost", b"localhost"):
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6) and not allowed(address[0]):
            raise RuntimeError("external network disabled by offline verification")
        return original_connect(sock, address)

    def connect_ex(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6) and not allowed(address[0]):
            raise RuntimeError("external network disabled by offline verification")
        return original_connect_ex(sock, address)

    def lookup(host, *args, **kwargs):
        if host is not None and not allowed(host):
            raise RuntimeError("external DNS disabled by offline verification")
        return original_lookup(host, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = lookup
