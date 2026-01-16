# MID Format Audit Report - Communication and Control MIDs

**Phase:** 02-mid-format-audit
**Plan:** 01
**Scope:** MID 0001-0005, MID 0040-0043, MID 9999
**Date:** 2026-01-16

## References

Specification sources consulted:
- [Atlas Copco Open Protocol Specification R280](https://s3.amazonaws.com/co.tulip.cdn/OpenProtocolSpecification_R280.pdf)
- [Open Protocol Specification R 2.16.0](https://asutp.org/Atlas_Copco/OpenProtocol_Specification_R_2.16.0.pdf)
- [Open Protocol Specification R 2.20.1](https://simonsobs.github.io/LAT_Alignment/latest/pdfs/OpenProtocol_Specification_R_2.20.1.pdf)
- [DOGA COM OPEN PROTOCOL Manual](https://www.doga.fr/sites/doga/files/uploads/documents/40719.pdf)
- [Working with Atlas Copco Open Protocol](https://medium.com/trainingcenter/working-with-atlas-copco-open-protocol-2feeaaf5c085)

---

## Open Protocol Message Structure Reference

### Header Format (20 bytes)

| Position | Bytes | Field | Format | Description |
|----------|-------|-------|--------|-------------|
| 0-3 | 4 | Length | ASCII digits | Total message length (0000-9999), excluding NUL terminator |
| 4-7 | 4 | MID | ASCII digits | Message ID (0001-9999) |
| 8-10 | 3 | Revision | ASCII digits | Message revision (000-999) |
| 11 | 1 | NoAck | ASCII digit | 0=ACK required, 1=No ACK needed |
| 12-13 | 2 | Station ID | ASCII | Station identifier or spaces |
| 14-15 | 2 | Spindle ID | ASCII | Spindle identifier or spaces |
| 16-19 | 4 | Spare | ASCII | Reserved, typically spaces |

### Message Terminator
- NUL character (0x00) terminates each message
- Length field does NOT include the NUL terminator

---

## MID 0001 - Communication Start Request

### Spec Reference
- Direction: Integrator -> Controller
- Purpose: Initiates communication session
- Data Field: None (header only)
- Revisions: 1-7 available per spec

### Current Implementation (lines 301-314)

```python
if mid_int == 1:
    if self.session_active: resp = build_message(4, rev=1, data="000196")
    else:
        requested_rev = int(rev) if rev.strip() else 1
        if requested_rev > 1: resp = build_message(4, rev=1, data="000197")
        else:
            # Success case - send MID 0002
```

### Deviations Found

| ID | Issue | Current Implementation | Expected per Spec | Severity |
|----|-------|------------------------|-------------------|----------|
| 0001-D1 | Revision rejection | Rejects any revision > 1 | Should support revisions 1-7 (or at least negotiate down) | **Major** |
| 0001-D2 | Error code format | "000196" (6 chars) | Per spec: 4-digit MID + 2-digit error = "000196" is correct | None |

### Notes
- Error code 96 = "Client already connected" - **Correct**
- Error code 97 = "MID revision unsupported" - **Correct**
- Header parsing appears correct for revision 1

---

## MID 0002 - Communication Start Acknowledge

### Spec Reference
- Direction: Controller -> Integrator
- Purpose: Confirms session established, provides controller info
- Revisions: 1-8 available per spec

### Revision 1 Data Fields (per spec)

| Field ID | Name | Length | Format |
|----------|------|--------|--------|
| 01 | Cell ID | 4 | ASCII digits |
| 02 | Channel ID | 2 | ASCII digits |
| 03 | Controller Name | 25 | ASCII string, space-padded |

### Current Implementation (lines 307-311)

```python
cell_id = "0001"; channel_id = "01"
data = f"01{cell_id}02{channel_id}03{self.controller_name}"
resp = build_message(2, rev=1, data=data)
```

### Deviations Found

| ID | Issue | Current Implementation | Expected per Spec | Severity |
|----|-------|------------------------|-------------------|----------|
| 0002-D1 | Field separator format | Uses field IDs directly in data | Spec uses field ID prefix format "01XXXX02YY03ZZZ..." | None (format appears correct) |
| 0002-D2 | Cell ID length | 4 digits ("0001") | 4 ASCII digits | None |
| 0002-D3 | Channel ID length | 2 digits ("01") | 2 ASCII digits | None |
| 0002-D4 | Controller name length | 25 chars (padded/truncated) | 25 ASCII chars | None |
| 0002-D5 | Multi-revision support | Only revision 1 | Spec defines revisions 1-8 with additional fields | **Major** |

### Notes
- Revision 1 format appears correct
- Higher revisions add: Software version, Tool software version, Serial number, Tool serial number, Station ID, Station name, etc.

---

## MID 0003 - Communication Stop

### Spec Reference
- Direction: Integrator -> Controller
- Purpose: Terminates communication session
- Data Field: None (header only)
- Response: MID 0005 (Command accepted)

### Current Implementation (lines 317-327)

```python
elif mid_int == 3:
    resp = build_message(5, rev=1, data="0003")
    self.send_to_client(resp)
    print("[Session] Communication stop received. Ending session.")
    self.session_active = False
    # ... cleanup
```

### Deviations Found

| ID | Issue | Current Implementation | Expected per Spec | Severity |
|----|-------|------------------------|-------------------|----------|
| 0003-D1 | Response format | Sends MID 0005 with data="0003" | Per spec: MID 0005 echoes back the received MID (0003) | None |

### Notes
- Implementation correctly responds with MID 0005 acknowledging MID 0003
- Properly cleans up session state and subscriptions

---

## MID 0004 - Command Error

### Spec Reference
- Direction: Controller -> Integrator
- Purpose: Indicates command failed
- Data Field: 4-digit MID + 2-digit error code (6 chars total)

### Error Code Format per Spec
```
Data = MMMMEE
Where:
  MMMM = 4-digit MID that failed
  EE = 2-digit error code
```

### Current Implementation (lines 302, 305, 329)

Used in responses:
```python
resp = build_message(4, rev=1, data="000196")  # MID 0001 error 96
resp = build_message(4, rev=1, data="000197")  # MID 0001 error 97
resp = build_message(4, rev=1, data="001802")  # MID 0018 error 02
```

### Deviations Found

| ID | Issue | Current Implementation | Expected per Spec | Severity |
|----|-------|------------------------|-------------------|----------|
| 0004-D1 | Data format | 6 chars "MMMMEE" | Spec: 4-digit MID + 2-digit error = 6 chars | None |

### Notes
- Error code format is correct: 4-digit MID + 2-digit error
- Common error codes used:
  - 96 = Client already connected
  - 97 = Revision unsupported
  - 02 = Parameter set not found (for MID 0018)
  - 06 = Already subscribed
  - 07 = Not subscribed

---

## MID 0005 - Command Accepted

### Spec Reference
- Direction: Controller -> Integrator
- Purpose: Acknowledges successful command
- Data Field: 4-digit MID being acknowledged

### Current Implementation (lines 318, 349, 356, etc.)

```python
resp = build_message(5, rev=1, data="0003")  # Ack for MID 0003
resp = build_message(5, rev=1, data="0042")  # Ack for MID 0042
resp = build_message(5, rev=1, data="0043")  # Ack for MID 0043
```

### Deviations Found

| ID | Issue | Current Implementation | Expected per Spec | Severity |
|----|-------|------------------------|-------------------|----------|
| 0005-D1 | Data field format | 4-digit MID echo | Spec: Echo 4-digit MID of accepted command | None |

### Notes
- Format is correct - echoes back the 4-digit MID that was accepted
- Used consistently throughout codebase

---

## MID 0040 - Tool Disabled (Notification)

### Spec Reference
- Direction: Controller -> Integrator
- Purpose: Notifies integrator that tool has been disabled
- Data Field: None in revision 1

### Current Implementation (lines 340-342)

```python
elif mid_int == 40:
    print("[Tool] Received Disable Tool Command (MID 0040) from client (unexpected). Ignoring.")
    return
```

### Deviations Found

| ID | Issue | Current Implementation | Expected per Spec | Severity |
|----|-------|------------------------|-------------------|----------|
| 0040-D1 | Direction handling | Ignores if received | Per spec: MID 0040 is Controller->Integrator, should not be received from client | None (correct behavior) |
| 0040-D2 | Missing outbound support | Never sends MID 0040 | Should send MID 0040 after tool disable to notify integrator | **Minor** |

### Notes
- Current code ignores MID 0040 if received from client - this is correct since MID 0040 flows from controller to integrator
- However, when tool is disabled (via MID 0042), spec indicates controller should send MID 0040 to notify the integrator
- Current implementation only sends MID 0005 acknowledgment, not MID 0040 notification

---

## MID 0041 - Tool Enabled (Notification)

### Spec Reference
- Direction: Controller -> Integrator
- Purpose: Notifies integrator that tool has been enabled
- Data Field: None in revision 1

### Current Implementation (lines 343-345)

```python
elif mid_int == 41:
    print("[Tool] Received Enable Tool Command (MID 0041) from client (unexpected). Ignoring.")
    return
```

### Deviations Found

| ID | Issue | Current Implementation | Expected per Spec | Severity |
|----|-------|------------------------|-------------------|----------|
| 0041-D1 | Direction handling | Ignores if received | Per spec: MID 0041 is Controller->Integrator, should not be received from client | None (correct behavior) |
| 0041-D2 | Missing outbound support | Never sends MID 0041 | Should send MID 0041 after tool enable to notify integrator | **Minor** |

### Notes
- Same situation as MID 0040 - ignoring inbound is correct
- Missing outbound notification when tool is enabled

---

## MID 0042 - Disable Tool Request

### Spec Reference
- Direction: Integrator -> Controller
- Purpose: Request controller to disable the tool
- Data Field: None in revision 1 (revision 2 adds tool number)
- Response: MID 0005 (ack) followed by MID 0040 (notification)

### Current Implementation (lines 346-352)

```python
elif mid_int == 42:
    print("[Tool] Received Request Tool Disable (MID 0042).")
    self.tool_enabled = False
    resp = build_message(5, rev=1, data="0042")
    self.send_to_client(resp)
    print("[Tool] Tool Disabled. Sent MID 0040 confirmation.")  # Log says 0040 but sends 0005
    return
```

### Deviations Found

| ID | Issue | Current Implementation | Expected per Spec | Severity |
|----|-------|------------------------|-------------------|----------|
| 0042-D1 | Response sequence | Only sends MID 0005 | Per spec: Should send MID 0005 (ack) AND MID 0040 (notification) | **Minor** |
| 0042-D2 | Log message error | Says "Sent MID 0040" but sends MID 0005 | Misleading log message | **Minor** |
| 0042-D3 | Multi-revision | Only handles revision 1 | Revision 2 adds tool number field | **Minor** |

### Notes
- The acknowledgment (MID 0005) is correct
- Missing the MID 0040 notification per spec
- Log message is misleading - says "Sent MID 0040" but actually sends MID 0005

---

## MID 0043 - Enable Tool Request

### Spec Reference
- Direction: Integrator -> Controller
- Purpose: Request controller to enable the tool
- Data Field: None in revision 1 (revision 2 adds tool number)
- Response: MID 0005 (ack) followed by MID 0041 (notification)

### Current Implementation (lines 353-359)

```python
elif mid_int == 43:
    print("[Tool] Received Request Tool Enable (MID 0043).")
    self.tool_enabled = True
    resp = build_message(5, rev=1, data="0043")
    self.send_to_client(resp)
    print("[Tool] Tool Enabled. Sent MID 0041 confirmation.")  # Log says 0041 but sends 0005
    return
```

### Deviations Found

| ID | Issue | Current Implementation | Expected per Spec | Severity |
|----|-------|------------------------|-------------------|----------|
| 0043-D1 | Response sequence | Only sends MID 0005 | Per spec: Should send MID 0005 (ack) AND MID 0041 (notification) | **Minor** |
| 0043-D2 | Log message error | Says "Sent MID 0041" but sends MID 0005 | Misleading log message | **Minor** |
| 0043-D3 | Multi-revision | Only handles revision 1 | Revision 2 adds tool number field | **Minor** |

### Notes
- Same issues as MID 0042
- The acknowledgment is correct, but missing the notification MID

---

## MID 9999 - Keep Alive

### Spec Reference
- Direction: Bidirectional (Integrator <-> Controller)
- Purpose: Maintain connection, prevent timeout
- Data Field: None
- Behavior: Controller mirrors received keep-alive back to integrator
- Timing: Should be sent every 10 seconds if no other traffic; controller timeout is 15 seconds

### Current Implementation (lines 331-336)

```python
elif mid_int == 9999:
    print("[KeepAlive] Received keep-alive message.")
    resp = build_message(9999, rev=1)
    self.send_to_client(resp)
    print("[KeepAlive] Echo back keep-alive message.")
```

### Deviations Found

| ID | Issue | Current Implementation | Expected per Spec | Severity |
|----|-------|------------------------|-------------------|----------|
| 9999-D1 | Echo behavior | Correct - echoes back MID 9999 | Per spec: Mirror received keep-alive | None |
| 9999-D2 | Timing enforcement | No timeout enforcement | Spec: 15-second timeout should close connection | **Major** |

### Notes
- Echo behavior is correct
- No implementation of the 15-second timeout - if client stops sending keep-alive, connection remains open indefinitely
- This is an emulator, so strict timeout enforcement may not be needed, but should be documented

---

## Summary

### Deviation Counts by Severity

| Severity | Count | Description |
|----------|-------|-------------|
| **Critical** | 0 | No critical deviations |
| **Major** | 3 | 0001-D1, 0002-D5, 9999-D2 |
| **Minor** | 8 | 0040-D2, 0041-D2, 0042-D1, 0042-D2, 0042-D3, 0043-D1, 0043-D2, 0043-D3 |
| **None** | 10 | Format implementations that are correct |

### Priority Fixes for Phase 3

1. **High Priority (Major):**
   - Add multi-revision support for MID 0001/0002 (currently rejects rev > 1)
   - Consider adding 15-second keep-alive timeout (or document as intentional omission)

2. **Medium Priority (Minor):**
   - Add MID 0040/0041 notifications after tool disable/enable
   - Fix misleading log messages in MID 0042/0043 handlers
   - Add revision 2 support for tool control MIDs

### Correct Implementations

The following are implemented correctly per spec:
- Header format (20 bytes with proper field positions)
- MID length calculation (excludes NUL terminator)
- MID 0004 error code format (4-digit MID + 2-digit error)
- MID 0005 acknowledgment format (echoes 4-digit MID)
- MID 0002 revision 1 data fields (Cell ID, Channel ID, Controller Name)
- MID 0003 response handling
- MID 9999 keep-alive echo behavior
- MID 0040/0041 inbound handling (correctly ignores)
