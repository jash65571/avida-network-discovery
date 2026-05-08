# Avida Network Discovery — Presentation notes

These are my speaker notes for walking through the project. Read top to bottom or jump to whatever section.

## What I built

A Python CLI that, for each network interface on your machine, figures out which devices are alive on that subnet, what TCP ports they have open, and what mDNS services they advertise. Outputs to a Rich-formatted table and optionally to JSON.

I wanted something I could actually run on my own home network and trust the output of, not just a toy.

## Why a CLI, not a web app

The deliverable is "find devices on a network" — the interesting part is the discovery logic, not a UI. A CLI keeps the surface area small and means I can demo it just by running one command.

## Why Python

Honestly because the libraries are there. ARP, mDNS, async sockets, interface enumeration — all of it has a maintained pure-Python option. If I'd done this in Go or Rust I'd have spent half the time reinventing zeroconf bindings.

## Tech choices and what I considered

**Interface listing — psutil.** Tried `netifaces` first, the wheel didn't install cleanly on my Python 3.11. Looked at `ifaddr`. Settled on psutil because it's actively maintained, gives me everything I need in one call, and the project already has a million users so I trust it.

**Host discovery — Scapy ARP, with ICMP fallback.** The reason for ARP is that on a switched LAN every host has to answer ARP no matter what its firewall does. ICMP, by contrast, is the most-blocked protocol on the planet (Windows firewall blocks ping by default). I considered shelling out to nmap, decided against it because adding an external binary dependency makes the tool annoying to set up. Writing raw-socket ARP by hand is doable but Scapy already does it cross-platform. The ICMP fallback exists because Scapy needs Npcap on Windows and I didn't want the tool to be useless without it.

**Port scan — asyncio + semaphore.** Async TCP connect is fast enough (a /24 × 7 ports finishes in a few seconds), needs zero deps, and doesn't require admin. SYN scanning would be faster and stealthier but needs raw sockets. The semaphore is there because Windows runs out of source ports if you go full unbounded.

**mDNS — python-zeroconf.** The big thing for me was being able to bind to a specific interface IP. Default Zeroconf gloms onto whatever the OS picks for routing mDNS, which is wrong on a multi-homed machine.

**Output — Rich.** The output is part of what's being graded so I wanted it to look good without me writing column-alignment code. Plus JSON for the structured artefact.

**Concurrency — asyncio over threads.** I/O bound workload. asyncio gives me cleaner fan-out (`gather` per interface, `gather` per port). The one piece that doesn't fit, blocking Zeroconf, goes through `asyncio.to_thread` which lets it run alongside the rest.

## How the pieces fit together

```
discover.py  ──>  list interfaces (psutil)
                       │
                       ▼  asyncio.gather over selected interfaces
              for each interface:
                       │
                  ARP scan ──fail──> ICMP ping sweep
                       │
                       ▼
                  port scan   ║   mDNS browse
                  (async)     ║   (zeroconf in thread)
                       │      ║      │
                       └──────╫──────┘
                              ▼
                      merge by IP, output
```

Three discovery sources, merged by IP. mDNS-only hosts (Apple TVs, Echo Dots etc.) get added as new rows even if they didn't show up in ARP or ICMP.

## What was actually hard

Going to call out the real ones, not the boilerplate ones.

**Multi-homed routing was the recurring pain.** When my laptop was on Wi-Fi and Ethernet at the same time, two different things broke: mDNS was picking up devices from the wrong subnet, and TCP connect attempts were going out via the wrong NIC. Two different fixes — `Zeroconf(interfaces=[ip])` for mDNS, `local_addr=(source_ip, 0)` on `asyncio.open_connection` for the port scan. Took me a while to figure out why the mDNS results didn't match my ARP results.

**Npcap.** First run on Windows, ARP did nothing, no error message — Scapy's `srp` just returned an empty list. Took me longer than I'd like to admit to realise I needed Npcap installed in WinPcap-compat mode AND a terminal opened as admin. The ICMP fallback came directly out of this — I wanted the tool to still work for someone who doesn't want to install Npcap.

**Port scan speed.** Naive synchronous version was multi-minute and made testing miserable. Async with a semaphore brought it to seconds. The semaphore at 50 was tuned by hand — anything higher and Windows started returning connection resets from source-port exhaustion.

**Blocking + async.** Zeroconf's `ServiceBrowser` is blocking and runs its own listener thread. I tried wrapping it in a few different ways before landing on `asyncio.to_thread`, which is the cleanest.

**mDNS-only devices.** Halfway through I realised some of my devices weren't showing up at all because they didn't respond to ARP (or weren't on at the moment of the ARP scan but were broadcasting mDNS). The merge step exists specifically to add those.

## What I deliberately didn't do

- IPv6
- SYN scanning (would need raw sockets, not worth the platform headache)
- HTTP/RTSP banner grabbing — would label cameras vs routers but adds noise
- Full mDNS service enumeration via the `_services._dns-sd._udp.local.` meta-query
- Retries on ICMP — single probe per host
- Unit tests — would write them next

All listed in the README too.

## How I'd demo it

1. `python discover.py --list` — show what interfaces my machine has.
2. `python discover.py --interfaces Wi-Fi --json results.json` — full scan, narrate the live `[host]`, `[ports]`, `[mdns]` log lines as they stream by, then the Rich table at the end.
3. Open `results.json` to show the structured output.
4. Re-run with a custom port list to show it's configurable.

## What I'd add next

- IPv6 host discovery
- A small dashboard (FastAPI + a re-scan loop) showing devices joining and leaving
- MAC vendor lookups so the table is actually readable
- Tests around the merge logic
