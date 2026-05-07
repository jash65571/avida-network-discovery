import argparse
import asyncio

from src.host_discovery import discover_hosts
from src.interfaces import find_interfaces, get_interfaces
from src.mdns_scan import discover_mdns_services
from src.models import DeviceResult, InterfaceScanResult, MdnsService, NetworkInterface
from src.output import print_results, save_json
from src.port_scan import scan_ports_for_devices


DEFAULT_PORTS = [80, 443, 554, 8000, 8080, 8554, 5353]


def parse_ports(raw_ports: str) -> list[int]:
    return [
        int(port.strip())
        for port in raw_ports.split(",")
        if port.strip()
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discover devices on local network interfaces."
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List available non-loopback network interfaces.",
    )

    parser.add_argument(
        "--interfaces",
        nargs="*",
        help="Interface names to scan. Example: --interfaces Wi-Fi Ethernet",
    )

    parser.add_argument(
        "--ports",
        default=",".join(str(port) for port in DEFAULT_PORTS),
        help="Comma-separated ports to scan.",
    )

    parser.add_argument(
        "--json",
        help="Optional path to save JSON results.",
    )

    parser.add_argument(
        "--mdns-timeout",
        type=float,
        default=4.0,
        help="Seconds to listen for mDNS services.",
    )

    return parser


def print_interfaces(interfaces: list[NetworkInterface]) -> None:
    print()
    print("Available interfaces:")
    print()

    for index, interface in enumerate(interfaces, start=1):
        print(f"{index}. {interface.name}")
        print(f"   IP: {interface.ipv4}")
        print(f"   Netmask: {interface.netmask}")
        print(f"   MAC: {interface.mac or 'N/A'}")
        print(f"   Network: {interface.network}")
        print()


def attach_mdns_to_devices(
    devices: list[DeviceResult],
    mdns_services: list[MdnsService],
) -> list[DeviceResult]:
    device_by_ip = {device.ip: device for device in devices}

    for service in mdns_services:
        for ip in service.ip_addresses:
            if ip not in device_by_ip:
                device_by_ip[ip] = DeviceResult(ip=ip)

            device_by_ip[ip].mdns_services.append(service)

            if not device_by_ip[ip].hostname:
                device_by_ip[ip].hostname = service.name

    return list(device_by_ip.values())


async def scan_interface(
    interface: NetworkInterface,
    ports: list[int],
    mdns_timeout: float,
) -> InterfaceScanResult:
    print()
    print(f"=== Scanning interface: {interface.name} ===")
    print(f"IP: {interface.ipv4}")
    print(f"Network: {interface.network}")
    print()

    devices = await discover_hosts(interface)

    port_task = asyncio.create_task(
        scan_ports_for_devices(
            devices=devices,
            interface=interface,
            ports=ports,
        )
    )

    mdns_task = asyncio.to_thread(
        discover_mdns_services,
        interface,
        mdns_timeout,
    )

    scanned_devices, mdns_services = await asyncio.gather(port_task, mdns_task)

    merged_devices = attach_mdns_to_devices(scanned_devices, mdns_services)

    return InterfaceScanResult(
        interface=interface,
        devices=merged_devices,
    )


async def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    ports = parse_ports(args.ports)

    all_interfaces = get_interfaces()

    if args.list:
        print_interfaces(all_interfaces)
        return

    selected_interfaces = find_interfaces(args.interfaces)

    if not selected_interfaces:
        print("No matching interfaces found.")
        print_interfaces(all_interfaces)
        return

    print("SAFETY WARNING:")
    print("Only scan networks you own or have permission to test.")
    print("Some host discovery methods may require admin/root privileges.")
    print()

    results = await asyncio.gather(
        *[
            scan_interface(
                interface=interface,
                ports=ports,
                mdns_timeout=args.mdns_timeout,
            )
            for interface in selected_interfaces
        ]
    )

    print_results(results)

    if args.json:
        save_json(results, args.json)


if __name__ == "__main__":
    asyncio.run(main())