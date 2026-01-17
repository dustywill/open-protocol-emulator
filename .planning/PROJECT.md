# Open Protocol Emulator - PF6000 Expansion

## What This Is

A Python-based Open Protocol controller emulator that simulates an Atlas Copco PF6000 DC controller for integration testing. It allows software that interfaces with Atlas Copco torque tools to be tested without physical hardware, supporting configurable MID revisions (1-7) and controller profiles with GUI-based configuration.

## Core Value

Correct Open Protocol message formats that match the official specification exactly, enabling reliable integration testing against properly-implemented MID responses with revision flexibility.

## Requirements

### Validated

- ✓ TCP server with Open Protocol communication — v1.0
- ✓ MID 0001-0003 communication start/stop — v1.0
- ✓ MID 0004 error responses — v1.0
- ✓ MID 0005 command acknowledgment — v1.0
- ✓ MID 0014-0018 parameter set selection — v1.0
- ✓ MID 0042-0043 tool enable/disable — v1.0
- ✓ MID 0050-0054 VIN handling — v1.0
- ✓ MID 0060-0063 tightening results — v1.0
- ✓ MID 9999 keep-alive — v1.0
- ✓ Tkinter GUI for emulator control — v1.0
- ✓ Pset parameter persistence (JSON) — v1.0
- ✓ VIN auto-increment on batch completion — v1.0
- ✓ Audit existing MID implementations against Open Protocol specification — v1.0
- ✓ Fix spec deviations in existing MID handlers — v1.0
- ✓ MID 0082 - Set time — v1.0
- ✓ MID 0100-0103 - Multi-spindle controllers — v1.0
- ✓ MID 0214-0215 - I/O device status — v1.0
- ✓ MID 0216-0219 - Relay functions — v1.0
- ✓ Configurable MID revision levels per-MID — v1.0
- ✓ Controller profiles (legacy, pf6000-basic, pf6000-full) — v1.0
- ✓ GUI controls for revision configuration — v1.0

### Active

(None - v1.0 milestone complete)

### Out of Scope

- Full Open Protocol MID coverage — only MIDs needed for testing, not the entire spec
- Multi-client support — single-client design is sufficient for testing purposes

## Context

**Current State (v1.0 shipped):**
- 2,091 lines of Python
- Single file with registry-based MID dispatch
- 8 controller-originated MIDs with multi-revision support
- 3 built-in controller profiles + custom profile save/load
- GUI with revision configuration panel and profile management

**Technical Stack:**
- Python stdlib only (zero dependencies)
- Tkinter for GUI
- JSON for persistence (Pset parameters, custom profiles)
- TCP socket server with daemon threads

## Constraints

- **Language**: Python (existing codebase)
- **Dependencies**: Python stdlib only — zero-dependency approach
- **GUI**: Tkinter interface
- **Protocol Compliance**: Matches official Open Protocol specification

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Expand Python codebase vs rewrite | Existing code works, faster to expand than rewrite | ✓ Good |
| Per-MID + Profile revision config | User needs both granular control and convenience presets | ✓ Good |
| Priority: Formats → MIDs → Revisions | Correct existing code first, then add features | ✓ Good |
| Use RLock for thread safety | Reentrancy needed when methods call other methods | ✓ Good |
| Registry pattern for MID dispatch | Adding new MIDs requires only handler + registration | ✓ Good |
| Field accumulation for multi-revision | Use if revision >= N pattern for additive fields | ✓ Good |
| Controllers folder for custom profiles | Auto-save to dedicated folder, appears in dropdown | ✓ Good |

---
*Last updated: 2026-01-17 after v1.0 milestone*
