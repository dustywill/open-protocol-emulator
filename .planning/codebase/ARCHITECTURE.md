# Architecture

**Analysis Date:** 2026-01-16

## Pattern Overview

**Overall:** Single-file Monolithic Application with Event-driven Message Dispatch

**Key Characteristics:**
- Single Python file (811 lines) containing all application logic
- TCP server with message-based protocol handling
- Integrated Tkinter GUI running in main thread
- Multi-threaded architecture with daemon threads

## Layers

**Message Protocol Layer:**
- Purpose: Handle Open Protocol message formatting and encoding
- Contains: `build_message()` helper function
- Location: `open_protocol_emulator.py:13-33`
- Depends on: Python stdlib only
- Used by: All message sending operations

**Server Communication Layer:**
- Purpose: TCP socket management and client connections
- Contains: `start_server()`, `handle_client()`, `send_to_client()`
- Location: `open_protocol_emulator.py:188-243`
- Depends on: Message Protocol Layer, Python socket/threading
- Used by: Protocol Message Dispatch Layer

**Protocol Message Dispatch Layer:**
- Purpose: Central message router that dispatches based on MID (Message ID)
- Contains: `process_message()` with 22+ MID handlers
- Location: `open_protocol_emulator.py:274-448`
- Depends on: Server Communication Layer, State Management Layer
- Used by: Client connection handlers

**State Management & Business Logic Layer:**
- Purpose: Manage emulator state and business rules
- Contains: VIN parsing/increment, Pset management, tightening simulation
- Location: `open_protocol_emulator.py:35-187`, `451-563`
- Depends on: Data Persistence Layer
- Used by: Protocol Dispatch, GUI

**Data Persistence Layer:**
- Purpose: JSON-based Pset parameter storage
- Contains: `_load_pset_parameters()`, `_save_pset_parameters()`, `_get_pset_filename()`
- Location: `open_protocol_emulator.py:96-133`
- Depends on: Python json, file I/O
- Used by: State Management Layer, GUI

**User Interface Layer:**
- Purpose: Tkinter GUI for configuration and monitoring
- Contains: `start_gui()` with settings frames and callbacks
- Location: `open_protocol_emulator.py:564-784`
- Depends on: All other layers
- Used by: Main entry point

## Data Flow

**TCP Client Connection:**

1. Client connects to TCP server (`start_server()` accepts connection)
2. New thread spawned for client handling (`handle_client()`)
3. Message bytes received and buffered
4. Complete messages extracted based on length header
5. `process_message()` dispatches to appropriate MID handler
6. Handler processes request, updates state, sends response
7. Thread-safe `send_to_client()` transmits response

**Tightening Result Simulation:**

1. Auto-send loop checks `auto_send_loop_active` flag
2. If active and subscribed, generates tightening result
3. Result data formatted per Open Protocol MID 0061 spec
4. Sent to client via `send_to_client()`
5. Batch counter incremented, VIN incremented on batch completion

**State Management:**
- File-based: Pset parameters saved/loaded as JSON
- In-memory: Session state, VIN, batch counters
- Each client connection resets counters but preserves Pset params

## Key Abstractions

**Message Format:**
- Purpose: Encapsulate Open Protocol frame structure
- Location: `build_message()` at `open_protocol_emulator.py:13-33`
- Pattern: Factory function returning bytes
- Format: `[LENGTH][MID][REV][ACK][STATION][SPINDLE][SPARE][DATA][NUL]`

**Subscription Pattern:**
- Purpose: Track client subscriptions for async events
- Examples: `vin_subscribed`, `result_subscribed`, `pset_subscribed`
- Pattern: Boolean flags with no-ack options

**Pset Parameter Registry:**
- Purpose: Store configuration per Parameter Set
- Location: `self.pset_parameters` dictionary
- Pattern: Dictionary keyed by Pset ID with torque/angle/batch settings

**VIN Parser:**
- Purpose: Extract prefix and numeric suffix from VIN
- Location: `_parse_vin()`, `_increment_vin()` at `open_protocol_emulator.py:136-187`
- Pattern: Regex extraction with automatic increment

## Entry Points

**Main Entry:**
- Location: `open_protocol_emulator.py:787-810`
- Triggers: `python open_protocol_emulator.py [--port N] [--name NAME]`
- Responsibilities: Parse args, create emulator instance, start server thread, launch GUI

**Server Entry:**
- Location: `OpenProtocolEmulator.start_server()` at line 188
- Triggers: Called from main thread as daemon thread
- Responsibilities: TCP socket binding, accept loop, spawn client handlers

**GUI Entry:**
- Location: `OpenProtocolEmulator.start_gui()` at line 564
- Triggers: Called from main thread after server starts
- Responsibilities: Tkinter window, settings frames, status updates

## Error Handling

**Strategy:** Exception catching at boundaries with fallback to defaults

**Patterns:**
- Network errors: Catch and close connection gracefully
- JSON errors: Catch and initialize defaults
- Protocol errors: Send MID 0004 error response
- GUI errors: TclError caught in update loop

## Cross-Cutting Concerns

**Logging:**
- Console print statements with prefixed categories
- Format: `[Category] Message` (e.g., `[Server]`, `[VIN]`, `[Tightening]`)

**Validation:**
- Pset ID checked against `available_psets` set
- Protocol revision checked (only rev 1 supported)
- Subscription state checked before processing

**Thread Safety:**
- `send_lock` protects socket writes
- Daemon threads for server and result loop
- GUI runs in main thread

---

*Architecture analysis: 2026-01-16*
*Update when major patterns change*
