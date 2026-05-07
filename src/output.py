import json
from dataclasses import asdict

from rich.console import Console
from rich.table import Table

from .models import InterfaceScanResult


console = Console()


def print_results(results: list[InterfaceScanResult]) -> None:
    for result in results:
        interface = result.interface

        console.print()
        console.print(f"[bold cyan]Interface:[/bold cyan] {interface.name}")
        console.print(f"IP: {interface.ipv4} | Netmask: {interface.netmask} | MAC: {interface.mac or 'N/A'}")
        console.print(f"Network: {interface.network}")

        table = Table(title=f"Discovered devices on {interface.name}")

        table.add_column("IP")
        table.add_column("MAC")
        table.add_column("Hostname")
        table.add_column("Open Ports")
        table.add_column("mDNS Services")

        for device in result.devices:
            mdns_summary = "\n".join(
                f"{service.name} ({service.service_type}:{service.port})"
                for service in device.mdns_services
            )

            table.add_row(
                device.ip,
                device.mac or "N/A",
                device.hostname or "N/A",
                ", ".join(str(port) for port in device.open_ports) or "None",
                mdns_summary or "None",
            )

        console.print(table)


def save_json(results: list[InterfaceScanResult], path: str) -> None:
    data = [asdict(result) for result in results]

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)

    console.print(f"[green]Saved JSON results to {path}[/green]")