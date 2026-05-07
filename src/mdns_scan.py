import socket
import time

from zeroconf import IPVersion, ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf

from .models import MdnsService, NetworkInterface


COMMON_SERVICE_TYPES = [
    "_http._tcp.local.",
    "_https._tcp.local.",
    "_rtsp._tcp.local.",
    "_printer._tcp.local.",
    "_ipp._tcp.local.",
    "_workstation._tcp.local.",
]


def _decode_txt(properties: dict[bytes, bytes]) -> dict[str, str]:
    decoded: dict[str, str] = {}

    for key, value in properties.items():
        decoded_key = key.decode(errors="ignore") if isinstance(key, bytes) else str(key)

        if isinstance(value, bytes):
            decoded_value = value.decode(errors="ignore")
        else:
            decoded_value = str(value)

        decoded[decoded_key] = decoded_value

    return decoded


def _service_info_to_mdns(service_type: str, name: str, info: ServiceInfo) -> MdnsService:
    try:
        ip_addresses = info.parsed_addresses()
    except Exception:
        ip_addresses = []

        for raw_address in info.addresses:
            try:
                ip_addresses.append(socket.inet_ntoa(raw_address))
            except Exception:
                pass

    return MdnsService(
        service_type=service_type,
        name=name,
        ip_addresses=ip_addresses,
        port=info.port,
        txt=_decode_txt(info.properties),
    )


class MdnsListener(ServiceListener):
    def __init__(self, zc: Zeroconf):
        self.zc = zc
        self.services: list[MdnsService] = []

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name, timeout=1000)

        if not info:
            return

        service = _service_info_to_mdns(type_, name, info)
        self.services.append(service)

        print(f"[mdns] Found {service.name} on {service.ip_addresses}:{service.port}")

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.add_service(zc, type_, name)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        return


def discover_mdns_services(
    interface: NetworkInterface,
    timeout_seconds: float = 4.0,
) -> list[MdnsService]:
    print(f"[mdns] Listening on {interface.name} ({interface.ipv4})")

    zc = Zeroconf(
        interfaces=[interface.ipv4],
        ip_version=IPVersion.V4Only,
    )

    listener = MdnsListener(zc)
    browsers = []

    try:
        for service_type in COMMON_SERVICE_TYPES:
            browsers.append(ServiceBrowser(zc, service_type, listener))

        time.sleep(timeout_seconds)

        return listener.services
    finally:
        for browser in browsers:
            browser.cancel()

        zc.close()