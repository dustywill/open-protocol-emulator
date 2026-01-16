# MID Format Audit: Parameter Set and VIN MIDs

**Phase:** 02 - MID Format Audit
**Plan:** 02
**Scope:** MID 0014-0018 (Parameter Set), MID 0050-0054 (VIN)
**Date:** 2026-01-16

## Specification References

- Open Protocol Specification R2.8.0 / R2.16.0 (Atlas Copco)
- OpenProtocolInterpreter library (field position reference)
- Sources: [Atlas Copco Open Protocol Specification](https://s3.amazonaws.com/co.tulip.cdn/OpenProtocolSpecification_R280.pdf)

---

## MID 0014 - Parameter Set Selected Subscribe

### Spec Reference
- Direction: Integrator -> Controller
- Purpose: Subscribe to parameter set selection notifications
- Message Length: 0020 (20 bytes header + NUL)
- Data Field: None (empty data)

### Current Implementation (lines 378-390)

```python
elif mid_int == 14: # MID 0014 Parameter set selected subscribe
    if self.pset_subscribed: resp = build_message(4, rev=1, data="001406") # Error: Subscribed
    else:
        self.pset_subscribed = True
        resp = build_message(5, rev=1, data="0014") # Accept
        print("[Pset] Pset subscription accepted.")
        if self.current_pset:
            mid15_data = self.current_pset.rjust(3, '0')
            mid15_msg = build_message(15, rev=1, data=mid15_data)
            self.send_to_client(mid15_msg)
            print(f"[Pset] Sent current Pset (MID 0015): {self.current_pset}")
    self.send_to_client(resp)
```

### Deviations

| # | Field/Behavior | Spec Requirement | Current Implementation | Severity | Notes |
|---|----------------|------------------|------------------------|----------|-------|
| 1 | NoAck flag handling | Byte 12 indicates if acknowledgment needed (0=ack, 1=no ack) | Not parsed or stored | Minor | MID 0016 acknowledgment behavior should respect this flag |
| 2 | Revision support | Revision field in request (bytes 9-11) | Ignored; no revision validation | Minor | Should check supported revision and reject unsupported with error 97 |
| 3 | MID 0017 unsubscribe | MID 0017 required for unsubscribe flow | Not implemented | Major | Missing unsubscribe handler for parameter set subscription |

### Notes
- Error code 06 (already subscribed) is correctly used
- Immediate MID 0015 send on subscription is correct per spec
- MID 0005 acknowledgment format is correct

---

## MID 0015 - Parameter Set Selected

### Spec Reference (Revision 1)
- Direction: Controller -> Integrator
- Purpose: Notify integrator of selected parameter set
- Message Length: 0042 (Revision 1)
- Data Fields (Rev 1):
  - Parameter Set ID: position 20, 3 bytes (000-999)
  - Date of Last Change: position 23, 19 bytes (YYYY-MM-DD:HH:MM:SS)

### Spec Reference (Revision 2 - Additional Fields)
- Parameter Set Name: position 25, 25 bytes
- Rotation Direction: position 73, 1 byte
- Batch Size: position 76, 2 bytes
- Torque Min/Max/Target: positions 80/88/96, 6 bytes each
- Angle Min/Max/Target: positions 104/111/118, 5 bytes each
- First Target: position 125, 6 bytes
- Start Final Angle: position 133, 6 bytes

### Current Implementation

```python
mid15_data = self.current_pset.rjust(3, '0')
mid15_msg = build_message(15, rev=1, data=mid15_data)
```

### Deviations

| # | Field/Behavior | Spec Requirement | Current Implementation | Severity | Notes |
|---|----------------|------------------|------------------------|----------|-------|
| 1 | Message length | 0042 for Rev 1 (includes date of last change) | 0023 (only Pset ID, 3 bytes data) | Critical | Missing required field |
| 2 | Date of Last Change | 19 bytes at position 23 (YYYY-MM-DD:HH:MM:SS) | Not included | Critical | Required field missing entirely |
| 3 | Field position | Parameter Set ID at position 20 | Correct (position 20, 3 bytes) | N/A | Correct |
| 4 | Padding | Parameter Set ID should be 3 ASCII digits (000-999) | Uses rjust(3, '0') | N/A | Correct |

### Recommended Fix
Add date of last change field to MID 0015 response:
```python
date_str = self.pset_last_change.strftime("%Y-%m-%d:%H:%M:%S") if self.pset_last_change else datetime.datetime.now().strftime("%Y-%m-%d:%H:%M:%S")
mid15_data = self.current_pset.rjust(3, '0') + date_str
```

---

## MID 0016 - Parameter Set Selected Acknowledge

### Spec Reference
- Direction: Integrator -> Controller
- Purpose: Acknowledge receipt of MID 0015
- Message Length: 0020 (header only)
- Data Field: None

### Current Implementation (line 392)

```python
elif mid_int == 16: print("[Pset] Pset selected acknowledged by client (MID 0016).")
```

### Deviations

| # | Field/Behavior | Spec Requirement | Current Implementation | Severity | Notes |
|---|----------------|------------------|------------------------|----------|-------|
| 1 | Acknowledgment tracking | Should track that client acknowledged | Only logs, no state change | Minor | Could track for retry logic if NoAck=0 |
| 2 | Response | No response expected | No response sent | N/A | Correct |

### Notes
- Current behavior is acceptable for basic operation
- Full implementation would track acknowledgments and retry MID 0015 if not acknowledged within timeout

---

## MID 0017 - Parameter Set Selected Unsubscribe

### Spec Reference
- Direction: Integrator -> Controller
- Purpose: Unsubscribe from parameter set notifications
- Message Length: 0020 (header only)
- Response: MID 0005 on success, MID 0004 with error 07 if not subscribed

### Current Implementation
**NOT IMPLEMENTED**

### Deviations

| # | Field/Behavior | Spec Requirement | Current Implementation | Severity | Notes |
|---|----------------|------------------|------------------------|----------|-------|
| 1 | MID Handler | Handle MID 0017 unsubscribe request | Not implemented | Major | Missing entire MID handler |
| 2 | Error code 07 | Return 07 (subscription doesn't exist) if not subscribed | N/A | Major | Not applicable until MID implemented |

### Recommended Implementation
```python
elif mid_int == 17: # MID 0017 Parameter set selected unsubscribe
    if self.pset_subscribed:
        self.pset_subscribed = False
        resp = build_message(5, rev=1, data="0017")
        print("[Pset] Unsubscribed from Pset selection.")
    else:
        resp = build_message(4, rev=1, data="001707") # Error: Not subscribed
    self.send_to_client(resp)
```

---

## MID 0018 - Select Parameter Set

### Spec Reference
- Direction: Integrator -> Controller
- Purpose: Select a parameter set by ID
- Data Fields:
  - Parameter Set ID: position 20, 3 bytes (000-999)
- Response: MID 0005 on success, MID 0004 with error 02 (Pset not found)

### Current Implementation (lines 363-376)

```python
elif mid_int == 18: # MID 0018 Select Parameter set
    pset_id = data_field.strip()
    if pset_id in self.available_psets:
        self.current_pset = pset_id; self.pset_last_change = datetime.datetime.now()
        resp = build_message(5, rev=1, data="0018") # Accept
        print(f"[Pset] Pset {pset_id} selected.")
        if self.pset_subscribed:
            mid15_data = self.current_pset.rjust(3, '0')
            mid15_msg = build_message(15, rev=1, data=mid15_data)
            self.send_to_client(mid15_msg)
            print(f"[Pset] Sent MID 0015: {self.current_pset}")
    else: resp = build_message(4, rev=1, data="001802") # Error: Pset not found
    self.send_to_client(resp)
```

### Deviations

| # | Field/Behavior | Spec Requirement | Current Implementation | Severity | Notes |
|---|----------------|------------------|------------------------|----------|-------|
| 1 | Parameter Set ID parsing | 3-digit numeric field at position 20 | Uses data_field.strip() which is correct | N/A | Correct |
| 2 | Error code | 02 = Parameter set ID not found | Uses "001802" | N/A | Correct |
| 3 | MID 0015 notification | Send MID 0015 to subscribed clients on selection | Sends but missing date field (see MID 0015 deviation) | Critical | Inherits MID 0015 format issue |
| 4 | Pset 0 selection | Selecting Pset 0 should be allowed (no Pset selected) | "0" or "000" would fail available_psets check | Minor | Should handle Pset 0 specially |

### Notes
- Core selection logic is correct
- Error handling is correct
- MID 0015 notification inherits format deviation from MID 0015

---

## MID 0050 - Vehicle ID Number Download Request

### Spec Reference
- Direction: Integrator -> Controller
- Purpose: Download a VIN to the controller
- Data Fields:
  - VIN Number: position 20, 25 bytes (padded with spaces)
- Response: MID 0005 on success

### Current Implementation (lines 394-409)

```python
elif mid_int == 50: # MID 0050 VIN download request
    vin = data_field.strip()
    print(f"[VIN] Received VIN download: {vin}")
    if self._parse_vin(vin):
        self.current_vin = vin
        with self.state_lock:
            self.batch_counter = 0
        print("[VIN] Batch counter reset due to new VIN.")
    resp = build_message(5, rev=1, data="0050") # Accept
    self.send_to_client(resp)
    if self.vin_subscribed:
        vin_param = self.current_vin.ljust(25)[:25]
        vin_data = build_message(52, rev=1, data=vin_param, no_ack=self.vin_no_ack)
        self.send_to_client(vin_data)
        print(f"[VIN] Sent VIN update (MID 0052): {self.current_vin}")
```

### Deviations

| # | Field/Behavior | Spec Requirement | Current Implementation | Severity | Notes |
|---|----------------|------------------|------------------------|----------|-------|
| 1 | VIN field length | 25 characters, space-padded | Uses strip() on input, then ljust(25) on output | N/A | Correct handling |
| 2 | Station ID | May be required (0 or 1) per spec appendix | Not parsed or validated | Minor | May affect multi-station configurations |
| 3 | MID 0052 notification | Send to subscribed clients on VIN download | Correctly sends MID 0052 | N/A | Correct |
| 4 | Acknowledgment | MID 0005 with data "0050" | Correctly sent | N/A | Correct |

### Notes
- VIN download handling is largely correct
- VIN parsing and batch counter reset logic is appropriate
- Minor enhancement: validate station ID field

---

## MID 0051 - Vehicle ID Number Subscribe

### Spec Reference
- Direction: Integrator -> Controller
- Purpose: Subscribe to VIN notifications
- Data Fields (Rev 2+): May include identifier type
- NoAck Flag: Byte 12 (0=ack needed, 1=no ack)
- Supported Revisions: 0, 1, 2 (default 0)

### Current Implementation (lines 411-426)

```python
elif mid_int == 51: # MID 0051 VIN subscribe
    no_ack_flag = msg[11:12].decode('ascii')
    req_rev = int(rev) if rev.strip() else 1
    if req_rev > 1: resp = build_message(4, rev=1, data="005197") # Error: Revision
    elif self.vin_subscribed: resp = build_message(4, rev=1, data="005106") # Error: Subscribed
    else:
        self.vin_subscribed = True; self.vin_no_ack = (no_ack_flag == "1")
        resp = build_message(5, rev=1, data="0051") # Accept
        print("[VIN] Subscription accepted.")
        if self.current_vin:
            vin_param = self.current_vin.ljust(25)[:25]
            vin_data = build_message(52, rev=1, data=vin_param, no_ack=self.vin_no_ack)
            self.send_to_client(vin_data)
            print(f"[VIN] Sent current VIN (MID 0052): {self.current_vin}")
    self.send_to_client(resp)
```

### Deviations

| # | Field/Behavior | Spec Requirement | Current Implementation | Severity | Notes |
|---|----------------|------------------|------------------------|----------|-------|
| 1 | NoAck flag position | Byte 12 (index 11 in 0-based) | Uses msg[11:12] | N/A | Correct |
| 2 | Revision support | Revisions 0, 1, 2 supported | Only allows rev <= 1 | Minor | Rev 2 adds identifier type fields |
| 3 | Error code 97 | Unsupported revision | Uses "005197" | N/A | Correct |
| 4 | Error code 06 | Already subscribed | Uses "005106" | N/A | Correct |
| 5 | Immediate MID 0052 | Send current VIN on subscribe | Correctly sends | N/A | Correct |

### Notes
- NoAck flag handling is correct
- Error codes are correct
- Revision 2 support could be added for identifier type fields

---

## MID 0052 - Vehicle ID Number

### Spec Reference (Revision 1)
- Direction: Controller -> Integrator
- Purpose: Notify integrator of current VIN
- Data Fields:
  - VIN Number: position 20, 25 bytes (space-padded)
- Revision 2: Adds identifier type and up to 4 identifier parts (25 bytes each)

### Current Implementation

```python
vin_param = self.current_vin.ljust(25)[:25]
vin_data = build_message(52, rev=1, data=vin_param, no_ack=self.vin_no_ack)
```

### Deviations

| # | Field/Behavior | Spec Requirement | Current Implementation | Severity | Notes |
|---|----------------|------------------|------------------------|----------|-------|
| 1 | VIN field length | 25 bytes, space-padded | Uses ljust(25)[:25] | N/A | Correct |
| 2 | NoAck flag | Set based on subscription NoAck | Correctly passed to build_message | N/A | Correct |
| 3 | Revision 2 fields | Identifier parts 2-4 | Not implemented | Minor | Future enhancement for Rev 2 |

### Notes
- Revision 1 format is correctly implemented
- VIN padding is correct (25 characters, space-padded)

---

## MID 0053 - Vehicle ID Number Acknowledge

### Spec Reference
- Direction: Integrator -> Controller
- Purpose: Acknowledge receipt of MID 0052
- Message Length: 0020 (header only)
- Data Field: None

### Current Implementation (line 428)

```python
elif mid_int == 53: print("[VIN] VIN event acknowledged by client (MID 0053).")
```

### Deviations

| # | Field/Behavior | Spec Requirement | Current Implementation | Severity | Notes |
|---|----------------|------------------|------------------------|----------|-------|
| 1 | Acknowledgment tracking | Should track acknowledgment for retry logic | Only logs | Minor | Similar to MID 0016 |
| 2 | Response | No response expected | None sent | N/A | Correct |

### Notes
- Basic acknowledgment logging is acceptable
- Full implementation would track for retry logic when NoAck=0

---

## MID 0054 - Vehicle ID Number Unsubscribe

### Spec Reference
- Direction: Integrator -> Controller
- Purpose: Unsubscribe from VIN notifications
- Response: MID 0005 on success, MID 0004 with error 07 if not subscribed

### Current Implementation (lines 430-436)

```python
elif mid_int == 54: # MID 0054 VIN unsubscribe
    if self.vin_subscribed:
        self.vin_subscribed = False; resp = build_message(5, rev=1, data="0054") # Accept
        print("[VIN] Unsubscribed from VIN updates.")
    else: resp = build_message(4, rev=1, data="005407") # Error: Not subscribed
    self.send_to_client(resp)
```

### Deviations

| # | Field/Behavior | Spec Requirement | Current Implementation | Severity | Notes |
|---|----------------|------------------|------------------------|----------|-------|
| 1 | Unsubscribe logic | Set vin_subscribed to false | Correctly implemented | N/A | Correct |
| 2 | Success response | MID 0005 with data "0054" | Correctly sent | N/A | Correct |
| 3 | Error code 07 | Not subscribed | Uses "005407" | N/A | Correct |

### Notes
- MID 0054 is correctly implemented
- Error handling matches spec

---

## Deviation Summary

### By Severity

| Severity | Count | MIDs Affected |
|----------|-------|---------------|
| Critical | 2 | MID 0015 (2 deviations) |
| Major | 2 | MID 0017 (not implemented), MID 0015 deviation inherited by MID 0018 |
| Minor | 6 | Various NoAck/revision/tracking issues |

### Critical Deviations Requiring Fix

1. **MID 0015 missing Date of Last Change field** - Message format non-compliant
2. **MID 0015 incorrect message length** - Should be 0042, currently 0023

### Major Deviations Requiring Fix

1. **MID 0017 not implemented** - Missing parameter set unsubscribe handler
2. **MID 0018 inherits MID 0015 format issue** - Notifications sent with wrong format

### Minor Deviations (Future Enhancement)

1. MID 0014: NoAck flag not parsed
2. MID 0014: Revision validation missing
3. MID 0016: Acknowledgment not tracked
4. MID 0018: Pset 0 selection not handled
5. MID 0050: Station ID not validated
6. MID 0051: Revision 2 not supported
7. MID 0053: Acknowledgment not tracked

---

## Recommendations for Phase 3

### Priority 1 (Critical)
1. Fix MID 0015 format to include Date of Last Change field
2. Update message length calculation for MID 0015

### Priority 2 (Major)
3. Implement MID 0017 (Parameter Set Selected Unsubscribe)
4. Add Pset 0 selection support to MID 0018

### Priority 3 (Minor - Optional)
5. Add NoAck flag handling to MID 0014
6. Add revision validation to MID 0014/0051
7. Add acknowledgment tracking for retry logic (MID 0016/0053)
8. Add Station ID validation for MID 0050

---

*Audit completed: 2026-01-16*
*Auditor: Claude Code*
