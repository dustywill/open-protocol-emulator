# Testing Patterns

**Analysis Date:** 2026-01-16

## Test Framework

**Runner:**
- Not configured - No test framework implemented

**Assertion Library:**
- Not applicable

**Run Commands:**
```bash
# No test commands available - testing not implemented
# Manual testing via Node-RED or direct TCP connection
```

## Test File Organization

**Location:**
- No test files present
- No `tests/`, `__tests__/`, or `test/` directories

**Naming:**
- Not established

**Structure:**
```
# No test structure exists
# Recommended:
tests/
├── unit/
│   ├── test_build_message.py
│   ├── test_vin_parsing.py
│   └── test_pset_parameters.py
├── integration/
│   ├── test_protocol_exchange.py
│   └── test_session_lifecycle.py
└── conftest.py
```

## Test Structure

**Suite Organization:**
- Not established

**Patterns:**
- Not established

## Mocking

**Framework:**
- Not applicable

**Patterns:**
- Not established

**What to Mock (recommendations):**
- Socket operations for protocol testing
- File I/O for persistence testing
- Tkinter for GUI testing

## Fixtures and Factories

**Test Data:**
- Not established

**Location:**
- Not established

## Coverage

**Requirements:**
- Not established

**Configuration:**
- No coverage tools configured

## Test Types

**Unit Tests:**
- Not implemented
- Candidates: `build_message()`, `_parse_vin()`, `_increment_vin()`

**Integration Tests:**
- Not implemented
- Candidates: Protocol message exchange, session lifecycle

**E2E Tests:**
- Manual testing via Node-RED test flow
- File: `node-red-testflow_open_protocol.json`
- Docker Compose setup for integration testing

## Common Patterns

**Manual Testing Approach:**
```bash
# Start emulator
python open_protocol_emulator.py --port 4545 --name TestController

# Start Node-RED for integration testing
docker compose up -d

# Access Node-RED at http://localhost:1880
# Import test flow from node-red-testflow_open_protocol.json
```

**Snapshot Testing:**
- Not used

## Recommended Test Implementation

**Add pytest Configuration:**
```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_functions = "test_*"

[tool.coverage.run]
source = ["."]
omit = ["tests/*"]
```

**Unit Test Examples:**
```python
# tests/unit/test_build_message.py
def test_build_message_basic():
    result = build_message(1, rev=1, data="")
    assert result.startswith(b"0024")
    assert b"0001" in result
    assert result.endswith(b"\x00")

def test_build_message_with_data():
    result = build_message(2, rev=1, data="test")
    assert b"test" in result
```

**Integration Test Examples:**
```python
# tests/integration/test_protocol_exchange.py
def test_communication_start():
    # Connect to emulator
    # Send MID 0001
    # Verify MID 0002 response
    pass
```

## Test Coverage Gaps

**Critical Gaps:**
- Protocol message format validation (MID 0001-0063)
- VIN parsing and increment logic
- Pset parameter load/save
- Error response handling

**Recommended Priority:**
1. `build_message()` - Core protocol formatting
2. `_parse_vin()`, `_increment_vin()` - VIN handling
3. `_load_pset_parameters()`, `_save_pset_parameters()` - Persistence
4. `process_message()` - MID dispatch (requires mocking)

---

*Testing analysis: 2026-01-16*
*Update when test patterns change*
