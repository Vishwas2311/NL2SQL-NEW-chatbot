"""Shared private endpoint policy; inference and embeddings keep separate protocols."""

import ipaddress
import socket
import ssl
from pathlib import Path
from urllib.parse import urlparse

import httpx


def private_endpoint(url: str | None, approved_hosts: tuple[str, ...]) -> None:
    """Only approved private hosts, verified TLS, or loopback HTTP are accepted."""
    endpoint = urlparse(url or "")
    if (
        endpoint.hostname not in approved_hosts
        or endpoint.username
        or endpoint.password
        or endpoint.query
        or endpoint.fragment
        or endpoint.scheme not in ("https", "http")
    ):
        raise ValueError("Endpoint must match a specifically approved private host")
    addresses = socket.getaddrinfo(
        endpoint.hostname, endpoint.port or (443 if endpoint.scheme == "https" else 80)
    )
    if any(not ipaddress.ip_address(item[4][0]).is_private for item in addresses):
        raise ValueError("Public endpoints are prohibited")
    if endpoint.scheme == "http" and endpoint.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Remote private inference requires TLS")


def private_client(ca_bundle: Path | None) -> httpx.Client:
    """No inherited proxy, redirect or disabled TLS verification."""
    return httpx.Client(
        trust_env=False, follow_redirects=False, verify=ssl.create_default_context(cafile=ca_bundle)
    )
