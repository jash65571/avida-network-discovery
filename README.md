# Avida Multi-Interface Network Device Discovery Tool

Python command-line tool for discovering devices on local network interfaces.

## Safety warning

Only run this tool on networks you own or have permission to test.

Some discovery methods may require admin/root privileges.

The tool uses a conservative local-network scan and does not scan public IP ranges.

## Features

- Lists non-loopback network interfaces
- Shows interface name, IPv4, netmask, MAC, and subnet
- Allows selecting one or more interfaces
- Performs ARP discovery where available
- Falls back to ICMP ping sweep
- Performs asynchronous port scanning
- Scans common IoT/security ports:
  - 80
  - 443
  - 554
  - 8000
  - 8080
  - 8554
  - 5353
- Performs mDNS / ZeroConf discovery
- Groups output by interface
- Saves optional JSON output

## Setup

```bash
python -m venv .venv