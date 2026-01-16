# Technology Stack

**Analysis Date:** 2026-01-16

## Languages

**Primary:**
- Python 3.x - All application code (`open_protocol_emulator.py`)

**Secondary:**
- JavaScript/Node.js - Node-RED integration via npm

## Runtime

**Environment:**
- Python 3.x (no specific version pinned - `README.md` states "Python 3.x")
- Node.js - via Node-RED Docker image (no .nvmrc file)

**Package Manager:**
- npm - Used for Node-RED and `node-red-contrib-open-protocol` - `docker-compose.yml:36`, `Dockerfile:3`
- No Python package manager files (requirements.txt, Pipfile, pyproject.toml)
- No npm lockfile in repo

## Frameworks

**Core:**
- None (vanilla Python with stdlib)

**Testing:**
- Not configured - No test framework implemented

**Build/Dev:**
- Docker - Containerization for Node-RED integration
- Docker Compose v3.7 - Multi-service orchestration

## Key Dependencies

**Critical (Python stdlib only):**
- `socket` - TCP/IP networking for Open Protocol communication - `open_protocol_emulator.py:2`
- `threading` - Multi-threaded server handling - `open_protocol_emulator.py:3`
- `tkinter` - GUI framework for control interface - `open_protocol_emulator.py:7-8`
- `argparse` - Command-line argument parsing - `open_protocol_emulator.py:10`
- `json` - Parameter persistence (imported locally) - `open_protocol_emulator.py:105, 126`

**Infrastructure (Node-RED):**
- `node-red-contrib-open-protocol` - npm package for Open Protocol node support - `Dockerfile:3`

## Configuration

**Environment:**
- Command-line arguments: `--port` / `-p` (default: 4545), `--name` / `-n` (default: "OpenProtocolSim")
- Docker environment: `TZ=Europe/Amsterdam` - `docker-compose.yml:15`
- No .env files required

**Build:**
- `Dockerfile` - Node-RED container with open-protocol node
- `docker-compose.yml` - Multi-port service configuration

**File-based:**
- Pset parameters stored as `pset_parameters_{controller_name}.json`
- `.gitignore` excludes: `pset_parameters_*.json`

## Platform Requirements

**Development:**
- Any platform with Python 3.x
- No external Python dependencies (stdlib only)
- Tkinter for GUI (included in standard Python)

**Production:**
- Python 3.x runtime
- Docker (optional) for Node-RED integration
- TCP port access (4545 default, 5000-5010 for multiple instances)

**Deployment:**
- Standalone Python script execution
- Docker container with Node-RED (optional)
- Port mappings: 1880 (Node-RED), 4545 (Open Protocol), 5000-5010 (multiple instances)

---

*Stack analysis: 2026-01-16*
*Update after major dependency changes*
