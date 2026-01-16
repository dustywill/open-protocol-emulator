# Coding Conventions

**Analysis Date:** 2026-01-16

## Naming Patterns

**Files:**
- snake_case for Python files: `open_protocol_emulator.py`
- kebab-case with descriptive names for JSON: `node-red-testflow_open_protocol.json`
- UPPERCASE for project files: `README.md`, `LICENSE`

**Functions:**
- snake_case for all functions: `build_message()`, `start_server()`, `handle_client()`
- Underscore prefix for private methods: `_parse_vin()`, `_increment_vin()`, `_load_pset_parameters()`
- camelCase for GUI callbacks (nested functions): `apply_global_settings()`, `toggle_auto_send_loop()`

**Variables:**
- snake_case for instance variables: `self.session_active`, `self.current_pset`
- Suffix `_var` for Tkinter StringVar: `vin_var`, `batch_size_var`
- Suffix `_frame` for Tkinter frames: `settings_frame`, `control_frame`

**Types:**
- PascalCase for classes: `OpenProtocolEmulator`

## Code Style

**Formatting:**
- 4-space indentation (PEP 8)
- UTF-8 encoding with CRLF line endings (Windows)
- Semicolons used for compact conditional statements (non-PEP 8)

**Strings:**
- Single quotes for regular strings: `'0.0.0.0'`
- F-strings for interpolation: `f"{mid:04d}"`
- Escape sequences in f-strings: `\x00`

**Linting:**
- No linting tools configured
- No .pylintrc or pyproject.toml

## Import Organization

**Order:**
1. Standard library imports (socket, threading, time, datetime)
2. GUI imports (tkinter)
3. Utility imports (re, argparse)
4. Lazy imports within methods (json)

**Grouping:**
- No blank lines between groups
- Import statements at top of file

**Path Aliases:**
- Not applicable (single-file project)

## Error Handling

**Patterns:**
- Try/except at boundaries (network, file I/O)
- Specific exceptions: `OSError`, `BrokenPipeError`, `ConnectionResetError`
- Fallback to defaults on error

**Error Types:**
- Network errors: Close connection, log message
- File errors: Initialize defaults, continue
- Protocol errors: Send MID 0004 error response

## Logging

**Framework:**
- Console print statements (no logging framework)
- Prefixed categories for filtering

**Patterns:**
- Format: `print(f"[Category] Message")`
- Categories: `[Server]`, `[Client]`, `[VIN]`, `[Tightening]`, `[Pset]`, `[Tool]`, `[GUI]`, `[Session]`, `[Error]`

## Comments

**When to Comment:**
- Section separators: `# --- VIN and Batch State ---`
- Inline clarification: `# Use passed-in port`
- Protocol notes: `# MID 0001: Communication start`

**JSDoc/TSDoc:**
- Not applicable (Python project)

**Docstrings:**
- Triple-quote format: `"""Description."""`
- Present tense, brief descriptions
- Used for functions and methods

**TODO Comments:**
- None present in codebase

## Function Design

**Size:**
- Most functions under 50 lines
- Exception: `process_message()` at ~177 lines (needs refactoring)
- Exception: `start_gui()` at ~220 lines

**Parameters:**
- Type hints on function signatures: `def build_message(mid: int, rev: int = 1)`
- Default values for optional parameters
- No dataclass/TypedDict for options (positional parameters used)

**Return Values:**
- Explicit returns with type hints: `-> bytes`
- Early returns for error cases
- No Result type pattern

## Module Design

**Exports:**
- Single file, no module system
- Single class (`OpenProtocolEmulator`) + helper function (`build_message`)

**Barrel Files:**
- Not applicable (single file)

## Thread Safety Conventions

**Locks:**
- `self.send_lock = threading.Lock()` for socket writes
- No locks for state variables (known issue)

**Daemon Threads:**
- All background threads marked as daemon=True
- Prevents blocking on exit

---

*Convention analysis: 2026-01-16*
*Update when patterns change*
