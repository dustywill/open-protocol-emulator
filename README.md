# Open Protocol Controller Emulator

A Python-based emulator for Open Protocol controllers (Atlas Copco, Panasonic, etc.). Designed for testing and development, allowing you to simulate controller communication without physical hardware.

## Requirements

- Python 3.x
- customtkinter

## Installation

```bash
pip install customtkinter
```

## Running the Emulator

```bash
python open_protocol_emulator.py
```

This starts the server on port 4545 and launches the GUI.

### Command-line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `-p`, `--port` | Port number to listen on | 4545 |
| `-n`, `--name` | Controller name (reported in MID 0002) | OpenProtocolSim |

Example:
```bash
python open_protocol_emulator.py --port 5000 --name MyController
```

## Features

### Communication
- Full Open Protocol message handling with configurable MID revisions
- Keep-alive support (MID 9999)
- Multi-revision support for most MIDs

### Tightening Simulation
- Single tightening results (MID 0061, revisions 1-7)
- Multi-spindle results (MID 0101, revisions 1-5)
- Configurable OK/NOK probability
- Automatic or manual result triggering

### Parameter Sets (PSets)
- 24 configurable PSets (001-005, 010-015, 050-055, 100-105)
- Per-PSet settings: batch size, torque limits, angle limits
- PSet parameters saved to JSON file per controller name

### I/O and Relays
- Relay function subscription and status (MID 0216/0217/0219)
- Configurable relay mappings (trigger, forward, reverse)
- GUI toggle switches for relay control

### Controller Profiles
- Built-in profiles: legacy, pf6000-basic, pf6000-full
- Save/load custom profiles with revision and relay configurations
- Profiles stored in `controllers/` folder as JSON

### VIN Management
- VIN subscription and download (MID 0050/0051/0052)
- Auto-incrementing VIN support

### Tool Control
- Tool enable/disable (MID 0042/0043)
- Tool data reporting (MID 0041)

## Implemented MIDs

| MID | Description | Revisions |
|-----|-------------|-----------|
| 0001 | Communication start | 1 |
| 0002 | Communication start acknowledge | 1-6 |
| 0003 | Communication stop | 1 |
| 0004 | Command error | 1-3 |
| 0005 | Command accepted | 1 |
| 0014 | Parameter set selected subscribe | 1 |
| 0015 | Parameter set selected | 1-2 |
| 0016 | Parameter set selected acknowledge | 1 |
| 0017 | Parameter set selected unsubscribe | 1 |
| 0018 | Select parameter set | 1 |
| 0040 | Tool data request | 1 |
| 0041 | Tool data reply | 1-5 |
| 0042 | Disable tool | 1 |
| 0043 | Enable tool | 1 |
| 0050 | VIN download request | 1 |
| 0051 | VIN subscribe | 1 |
| 0052 | VIN number | 1-2 |
| 0053 | VIN acknowledge | 1 |
| 0054 | VIN unsubscribe | 1 |
| 0060 | Tightening result subscribe | 1 |
| 0061 | Tightening result | 1-7 |
| 0062 | Tightening result acknowledge | 1 |
| 0063 | Tightening result unsubscribe | 1 |
| 0100 | Multi-spindle result subscribe | 1-5 |
| 0101 | Multi-spindle result | 1-5 |
| 0102 | Multi-spindle result acknowledge | 1 |
| 0103 | Multi-spindle result unsubscribe | 1 |
| 0214 | I/O device status request | 1-2 |
| 0215 | I/O device status reply | 1-2 |
| 0216 | Relay function subscribe | 1 |
| 0217 | Relay function status | 1 |
| 0218 | Relay function acknowledge | 1 |
| 0219 | Relay function unsubscribe | 1 |
| 9999 | Keep alive | 1 |

## GUI Overview

### GLOBAL Tab
- **Simulation Parameters**: VIN, batch size, NOK probability, auto-loop interval
- **Controls**: Toggle auto-loop, send single result
- **I/O Relays**: Direction (forward/reverse) and trigger toggle switches

### PSET CONFIG Tab
- Select and configure parameter sets
- Load/apply PSet settings
- Parameters: batch size, target torque, torque min/max, target angle, angle min/max

### REVISIONS Tab
- Configure maximum supported revision for each MID
- Load/save/apply controller profiles

### Status Panel
- Connection status
- Tool enabled/disabled state
- Current PSet and VIN
- Batch progress
- Auto-loop status
- Last tightening result
- Active subscriptions (VIN, PSet, Result, Multi-Spindle, Relays)

### Log Panel
- Real-time message logging
- Incoming/outgoing message display
- Optional file logging

## Files

| File | Description |
|------|-------------|
| `open_protocol_emulator.py` | Main application |
| `pset_parameters_<name>.json` | PSet configurations (auto-created) |
| `controllers/` | Custom controller profiles |

## Docker (Node-RED)

To run Node-RED with `node-red-contrib-open-protocol`:

```bash
docker compose build
docker compose up -d
```

Node-RED will be available at `http://localhost:1880`. Run the emulator separately on the host.

## Contributing

Contributions welcome for additional MIDs or features.

## License

GPL-3.0
