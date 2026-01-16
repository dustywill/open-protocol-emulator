# External Integrations

**Analysis Date:** 2026-01-16

## APIs & External Services

**Payment Processing:**
- Not applicable

**Email/SMS:**
- Not applicable

**External APIs:**
- Not applicable - This is a standalone emulator

## Data Storage

**Databases:**
- Not used - File-based storage only

**File Storage:**
- Local JSON files for Pset parameters
  - Pattern: `pset_parameters_{controller_name}.json`
  - Location: Project root directory
  - Format: JSON with indent=4
  - Load method: `_load_pset_parameters()` at `open_protocol_emulator.py:103`
  - Save method: `_save_pset_parameters()` at `open_protocol_emulator.py:126`

**Caching:**
- In-memory state only (no persistent cache)

## Authentication & Identity

**Auth Provider:**
- Not applicable - Open Protocol has no built-in authentication

**OAuth Integrations:**
- Not applicable

## Monitoring & Observability

**Error Tracking:**
- Console logging only (print statements)
- No external error tracking service

**Analytics:**
- Not implemented

**Logs:**
- stdout/stderr via print statements
- Prefixed categories: `[Server]`, `[Client]`, `[VIN]`, etc.

## CI/CD & Deployment

**Hosting:**
- Standalone Python script (local execution)
- Docker container with Node-RED (optional)

**CI Pipeline:**
- Not configured
- No GitHub Actions or similar

## Environment Configuration

**Development:**
- Required: Python 3.x
- Optional: Docker, Docker Compose
- No .env files required
- Configuration via command-line arguments

**Staging:**
- Not applicable (development tool)

**Production:**
- Not applicable (testing/development tool)

## Network Communication

**Open Protocol (Primary Integration):**
- Protocol: Open Protocol (industrial torque tool standard)
- Transport: TCP/IP sockets
- Default Port: 4545 (configurable via --port)
- Message Format: ASCII-encoded with binary length header
- Supported MIDs: 0001-0063, 9999 (Keep-alive)

**Node-RED Integration:**
- Package: `node-red-contrib-open-protocol` (npm)
- Connection: TCP to emulator port
- Test Flow: `node-red-testflow_open_protocol.json`
- Configuration in test flow:
  - Controller IP: Configurable (default 192.168.0.14)
  - Controller Port: 4545
  - Keep-Alive: 10000ms
  - Timeout: 3000ms
  - Retries: 3

## Docker Services

**Docker Compose Services:**
- Service: `node-red`
  - Image: `nodered/node-red` (custom build with open-protocol node)
  - Ports: 1880 (Node-RED UI), 4545 (Open Protocol), 5000-5010 (multiple instances)
  - Volume: `node-red-data:/data`
  - Network: `node-red-net`

**Container Configuration:**
- `Dockerfile`: Extends `nodered/node-red`, installs `node-red-contrib-open-protocol`
- `docker-compose.yml`: Service orchestration with port mappings

## Webhooks & Callbacks

**Incoming:**
- Not applicable - TCP socket-based communication only

**Outgoing:**
- Not applicable

## Industrial Device Support

**Supported Controllers (emulated):**
- Atlas Copco torque tools (Open Protocol standard)
- Panasonic torque tools
- Generic Open Protocol controllers

**Protocol Features:**
- Communication start/stop (MID 0001-0003)
- Error responses (MID 0004)
- Command acknowledgment (MID 0005)
- Parameter set selection (MID 0014-0018)
- Tool enable/disable (MID 0042-0043)
- VIN handling (MID 0050-0054)
- Tightening results (MID 0060-0063)
- Keep-alive (MID 9999)

---

*Integration audit: 2026-01-16*
*Update when adding/removing external services*
