from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NetworkInterface:
    name: str
    ipv4: str
    netmask: str
    mac: Optional[str]
    network: str


@dataclass
class MdnsService:
    service_type: str
    name: str
    ip_addresses: list[str]
    port: int
    txt: dict[str, str] = field(default_factory=dict)


@dataclass
class DeviceResult:
    ip: str
    mac: Optional[str] = None
    hostname: Optional[str] = None
    open_ports: list[int] = field(default_factory=list)
    mdns_services: list[MdnsService] = field(default_factory=list)


@dataclass
class InterfaceScanResult:
    interface: NetworkInterface
    devices: list[DeviceResult] = field(default_factory=list)