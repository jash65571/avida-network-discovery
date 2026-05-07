import asyncio

from .models import DeviceResult, NetworkInterface


async def _scan_one_port(
    ip: str,
    port: int,
    source_ip: str,
    timeout: float,
    semaphore: asyncio.Semaphore,
) -> int | None:
    async with semaphore:
        try:
            connection = asyncio.open_connection(
                host=ip,
                port=port,
                local_addr=(source_ip, 0),
            )

            reader, writer = await asyncio.wait_for(connection, timeout=timeout)

            writer.close()
            await writer.wait_closed()

            return port
        except Exception:
            return None


async def scan_ports_for_device(
    device: DeviceResult,
    interface: NetworkInterface,
    ports: list[int],
    timeout: float = 0.7,
) -> DeviceResult:
    semaphore = asyncio.Semaphore(50)

    tasks = [
        _scan_one_port(
            ip=device.ip,
            port=port,
            source_ip=interface.ipv4,
            timeout=timeout,
            semaphore=semaphore,
        )
        for port in ports
    ]

    results = await asyncio.gather(*tasks)

    device.open_ports = sorted([port for port in results if port is not None])

    if device.open_ports:
        print(f"[ports] {device.ip} open: {device.open_ports}")

    return device


async def scan_ports_for_devices(
    devices: list[DeviceResult],
    interface: NetworkInterface,
    ports: list[int],
) -> list[DeviceResult]:
    print(f"[ports] Scanning {len(devices)} device(s) on {interface.name}")

    tasks = [
        scan_ports_for_device(
            device=device,
            interface=interface,
            ports=ports,
        )
        for device in devices
    ]

    return await asyncio.gather(*tasks)