# Open Protocol Emulator - PF6000 Expansion

## What This Is

A Python-based Open Protocol controller emulator that simulates an Atlas Copco PF6000 DC controller for integration testing. It allows software that interfaces with Atlas Copco torque tools to be tested without physical hardware, supporting configurable MID revisions and controller profiles.

## Core Value

Correct Open Protocol message formats that match the official specification exactly, enabling reliable integration testing against properly-implemented MID responses with revision flexibility.

## Requirements

### Validated

- ✓ TCP server with Open Protocol communication — existing
- ✓ MID 0001-0003 communication start/stop — existing
- ✓ MID 0004 error responses — existing
- ✓ MID 0005 command acknowledgment — existing
- ✓ MID 0014-0018 parameter set selection — existing
- ✓ MID 0042-0043 tool enable/disable — existing
- ✓ MID 0050-0054 VIN handling — existing
- ✓ MID 0060-0063 tightening results — existing
- ✓ MID 9999 keep-alive — existing
- ✓ Tkinter GUI for emulator control — existing
- ✓ Pset parameter persistence (JSON) — existing
- ✓ VIN auto-increment on batch completion — existing

### Active

- [ ] Audit existing MID implementations against Open Protocol specification
- [ ] Fix any spec deviations in existing MID handlers
- [ ] Implement MID 0082 - Set time
- [ ] Implement MID 0100-0102 - Multi-spindle controllers
- [ ] Implement MID 0214-0215 - I/O device status
- [ ] Implement MID 0216-0218 - Relay functions
- [ ] Add configurable MID revision levels per-MID
- [ ] Add controller profiles (e.g., "PF6000 v1.8") that preset MID revisions
- [ ] GUI controls for revision configuration

### Out of Scope

- Full Open Protocol MID coverage — only MIDs needed for testing, not the entire spec
- Multi-client support — single-client design is sufficient for testing purposes

## Context

This is a brownfield project expanding an existing Open Protocol emulator. The codebase analysis (`.planning/codebase/`) identified:

**Technical Debt to Address:**
- Duplicate `_increment_vin()` method definition (lines 153-187) - first definition is broken
- Bare `except:` clauses in 5 locations hiding errors
- `process_message()` is a 177-line if/elif chain - consider refactoring to dispatch pattern
- Race conditions on shared state variables between threads

**Current Architecture:**
- Single Python file (811 lines) with monolithic structure
- Event-driven message dispatch via `process_message()`
- TCP server with daemon threads for client handling
- Tkinter GUI in main thread
- JSON file persistence for Pset parameters

**Reference Documentation:**
- User has access to official Atlas Copco Open Protocol specification document

## Constraints

- **Language**: Python (expanding existing codebase) — open to other languages but no reason to switch
- **Dependencies**: Prefer Python stdlib only — maintain current zero-dependency approach
- **GUI**: Keep existing Tkinter interface — expand rather than replace
- **Protocol Compliance**: Must match official Open Protocol specification exactly

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Expand Python codebase vs rewrite | Existing code works, faster to expand than rewrite | — Pending |
| Per-MID + Profile revision config | User needs both granular control and convenience presets | — Pending |
| Priority: Formats → MIDs → Revisions | Correct existing code first, then add features | — Pending |

---
*Last updated: 2026-01-16 after initialization*
