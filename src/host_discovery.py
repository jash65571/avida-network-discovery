import asyncio
import ipaddress
import platform
from typing import Optional

from .models import DeviceResult, NetworkInterface


def _try_arp_scan(interface: NetworkInterface, timeout: float = 2.0) -> list[DeviceResult]:
    try:
        from scapy.all import ARP, Ether, conf, srp
    except Exception:
        return []

    try:
        conf.verb = 0

        packet = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=interface.network)

        answered, _ = srp(
            packet,
            timeout=timeout,
            iface=interface.name,
        )

        devices: list[DeviceResult] = []

        for _, received in answered:
            devices.append(
                DeviceResult(
                    ip=received.psrc,
                    mac=received.hwsrc,
                )
            )

        return devices
    except Exception:
        return []


async def _ping_host(ip: str) -> Optional[DeviceResult]:
    system = platform.system().lower()

    if "windows" in system:
        command = ["ping", "-n", "1", "-w", "500", ip]
    else:
        command = ["ping", "-c", "1", "-W", "1", ip]

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

        await process.communicate()

        if process.returncode == 0:
            return DeviceResult(ip=ip)

        return None
    except Exception:
        return None


async def _icmp_ping_sweep(interface: NetworkInterface, limit: int = 254) -> list[DeviceResult]:
    network = ipaddress.ip_network(interface.network, strict=False)

    hosts = [str(host) for host in list(network.hosts())[:limit]]

    tasks = [_ping_host(ip) for ip in hosts]
    results = await asyncio.gather(*tasks)

    return [result for result in results if result is not None]


async def discover_hosts(interface: NetworkInterface) -> list[DeviceResult]:
    print(f"[host] Scanning {interface.name} subnet {interface.network}")

    arp_results = _try_arp_scan(interface)

    if arp_results:
        print(f"[host] ARP found {len(arp_results)} host(s)")
        return arp_results

    print("[host] ARP did not return results. Falling back to ICMP ping sweep.")
    ping_results = await _icmp_ping_sweep(interface)

    print(f"[host] ICMP found {len(ping_results)} host(s)")
    return ping_results