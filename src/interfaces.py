import ipaddress
import socket
from typing import Optional

import psutil

from .models import NetworkInterface


def _get_mac_for_interface(addresses) -> Optional[str]:
    for addr in addresses:
        if getattr(psutil, "AF_LINK", None) == addr.family:
            return addr.address

        if addr.family == getattr(socket, "AF_PACKET", None):
            return addr.address

        if ":" in addr.address or "-" in addr.address:
            if len(addr.address) >= 11:
                return addr.address

    return None


def get_interfaces() -> list[NetworkInterface]:
    interfaces: list[NetworkInterface] = []

    for name, addresses in psutil.net_if_addrs().items():
        ipv4 = None
        netmask = None

        for addr in addresses:
            if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                ipv4 = addr.address
                netmask = addr.netmask

        if not ipv4 or not netmask:
            continue

        network = ipaddress.ip_network(f"{ipv4}/{netmask}", strict=False)

        interfaces.append(
            NetworkInterface(
                name=name,
                ipv4=ipv4,
                netmask=netmask,
                mac=_get_mac_for_interface(addresses),
                network=str(network),
            )
        )

    return interfaces


def find_interfaces(selected_names: list[str] | None) -> list[NetworkInterface]:
    interfaces = get_interfaces()

    if not selected_names:
        return interfaces

    selected_lower = {name.lower() for name in selected_names}

    return [
        interface
        for interface in interfaces
        if interface.name.lower() in selected_lower
    ]