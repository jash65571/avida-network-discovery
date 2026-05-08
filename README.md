# Avida Network Discovery

Small Python CLI I wrote to find what's actually living on my home/office network. Pick an interface, it figures out which devices are up, what ports they have open, and what mDNS services they're advertising. Output goes to a Rich table, optionally to JSON.

Tested on Windows 11 (my main box) and a Linux VM. Should work on macOS too but I didn't get a chance to try it there.

## Quick warning

Don't run this against networks you don't own. ARP scans need admin / Npcap on Windows, sudo on Linux. The tool only ever touches the local subnet of whatever interface you point it at, so you can't accidentally hit something on the public internet, but still, be sensible.

## Running it

```
python -m venv .venv
.venv\Scripts\activate          # or source .venv/bin/activate on linux/mac
pip install -r requirements.txt

python discover.py --list
python discover.py --interfaces Wi-Fi
python discover.py --interfaces Wi-Fi Ethernet --json results.json
```

If you want different ports:

```
python discover.py --interfaces Wi-Fi --ports 22,80,443,8080
```

`--mdns-timeout` controls how long it sits and listens for mDNS announcements. Default is 4 seconds, which is usually enough.

Needs Python 3.11 or newer (I'm using `list[int] | None` and `asyncio.to_thread`).

## What's inside

```
discover.py            CLI entry, argparse, fans out across interfaces
src/
  models.py            dataclasses (NetworkInterface, DeviceResult, MdnsService, ...)
  interfaces.py        psutil interface listing
  host_discovery.py    ARP via scapy, with an ICMP ping sweep fallback
  port_scan.py         async TCP connect scan
  mdns_scan.py         zeroconf service browse pinned to one interface
  output.py            rich tables + json dump
results.json           sample output from one of my real scans
```

## Why these libraries

**psutil** because `psutil.net_if_addrs()` is the only thing I tried that gave me name + IPv4 + netmask + MAC in one shot across Windows and Linux. I started with `netifaces` and gave up after the wheel install kept breaking on Python 3.11.

**scapy** for ARP. ICMP gets blocked by host firewalls all the time but ARP basically can't be ignored on a switched LAN, and scapy hides all the raw-socket platform stuff. The downside is needing Npcap on Windows, which is why there's a fallback (see below).

**zeroconf** because it lets you bind to a specific interface IP. That matters more than you'd think on a multi-homed laptop — see the mDNS hurdle below.

**rich** mostly because the output is part of the deliverable and I wanted it to look good without writing formatting code. Could have used `tabulate` but Rich is nicer.

**asyncio** is stdlib. Port scanning and ICMP ping sweeps are textbook I/O bound, so async is a much better fit than threads, and we don't need an extra dep for it.

## How it works

For each interface you pick, the tool runs three things:

1. Host discovery. Tries an ARP scan first (fast, reliable, can't really be firewalled). If that fails or returns nothing — usually because Npcap isn't installed or you're not running as admin — it falls back to a concurrent ICMP ping sweep across the whole /24.
2. Port scan. Once we have a list of live IPs, opens async TCP connections to each port on each host. Bounded by a semaphore at 50 concurrent so we don't run out of source ports.
3. mDNS browse. Sits and listens on the interface for service announcements (HTTP, HTTPS, RTSP, IPP, printer, workstation).

Port scan and mDNS run in parallel. mDNS is blocking under the hood so it goes through `asyncio.to_thread`. Then the results get merged by IP — if mDNS sees a device that didn't show up in ARP/ICMP (Apple TVs do this, for instance), it gets added as its own row.

If you scan multiple interfaces at once they're all fanned out with `asyncio.gather`.

## Things that gave me trouble

**Scapy on Windows.** First run did nothing. Took me a while to realise it wanted Npcap installed in WinPcap-compatible mode AND an admin terminal. After that I wrapped the whole ARP path in `try/except` and added the ICMP fallback so the tool isn't useless if you don't have Npcap.

**mDNS on a multi-homed machine.** I had Wi-Fi and a tethered Ethernet at the same time. When I scanned Ethernet, mDNS was happily picking up devices from the Wi-Fi subnet because the OS was routing mDNS through whichever default route it preferred. Fix was passing `interfaces=[interface.ipv4]` to the `Zeroconf` constructor.

**Same problem with port scans, different fix.** Even after the mDNS thing, port scans on the "wrong" interface were going out via the default gateway. `asyncio.open_connection(..., local_addr=(source_ip, 0))` pins the source IP so the OS routes through the right NIC.

**Speed.** First version was synchronous. Scanning a /24 with 7 ports was multiple minutes, which made testing painful. Async + a semaphore got it down to a few seconds. The 50 came from trial and error — higher numbers started causing connection-reset errors on Windows from running out of ephemeral source ports.

**Blocking zeroconf in an async program.** `ServiceBrowser` doesn't fit into asyncio. I tried a few things before settling on `asyncio.to_thread`, which is dead simple and works.

## Stuff I left out on purpose

- IPv6. The home network's mostly IPv4 anyway and adding v6 doubles the discovery code paths for not much gain in practice.
- SYN scanning. TCP connect is slower and gets logged on the target, but works without raw sockets.
- HTTP banner grabbing. Open ports are reported as numbers, not "this is a Hikvision camera". Would be nice but adds time and false positives.
- The `_services._dns-sd._udp.local.` meta-query for mDNS. I just hard-coded six common service types. Meta-querying picks up everything but slows the scan.
- Retries. ICMP gets one 1-second probe and that's it. Real tooling would retry a couple of times.
- Tests. I know. With more time I'd at least cover the merge logic in `attach_mdns_to_devices`.

## Stuff I'd add next

- IPv6 ND-based host discovery
- MAC vendor lookup (OUI prefixes) so the table actually labels devices
- A `--watch` mode that re-scans every N seconds and shows joins/leaves
- Banner grabbing on HTTP and RTSP

## AI usage

Mostly used as a second pair of eyes. After I had the host discovery and port scan working, I pasted chunks into an LLM and asked things like "is there a more idiomatic way to do this" or "am I missing an edge case here". Most suggestions I either ignored (over-engineered) or partially adopted. A few that actually made it into the code:

- The semaphore around the async port scan. I'd written it without one initially and was getting weird connection-reset errors on Windows; the suggestion to bound concurrency was right on the money.
- The `local_addr=(source_ip, 0)` trick on `asyncio.open_connection`. I was trying to figure out why scans on a multi-homed box were going out the wrong NIC and this came up as a suggestion when I described the symptom.
- Wrapping the Scapy import in a try/except so the tool degrades gracefully when Npcap isn't installed, instead of crashing with an import error.

Things I rejected: a suggestion to switch to `aiohttp` for HTTP banner grabbing (out of scope), a suggestion to add a retry decorator on every network call (more complexity than the failure modes warrant), and a suggestion to write the output module as a class hierarchy with abstract base classes (not needed for two output formats).

I also ran the finished README through it once asking for feedback on clarity and reorganised a couple of sections based on what came back. Nothing was copy-pasted wholesale.

## Sample output

`results.json` in the repo is a real scan from my home network. Gateway at `192.168.1.1` showing 80/443, plus a handful of silent devices that probably have host firewalls (Roku, a couple of Echo Dots, etc).

## Time spent

*Roughly 12 hours. Most of that was the multi-homed routing problems described above and getting Npcap working — the actual code is pretty short.*
