# MID 0060-0063 Tightening Result Format Audit

**Audit Date:** 2026-01-16
**Plan:** 02-03
**Auditor:** Claude Code
**Spec Reference:** Open Protocol Specification R2.8.0, Section 5.8

---

## MID 0060 - Last Tightening Result Data Subscribe

### Spec Reference
Open Protocol R2.8.0 - MID 0060 is a subscribe request from integrator to controller.

**Per Specification:**
- Message format: Standard header only (no data fields required)
- Revision field (bytes 8-10): Specifies which revision of MID 0061 the integrator wants
- NoAck flag (byte 11): Controls whether MID 0062 acknowledgment is needed for each MID 0061
- Subscribe determines the revision of MID 0061 responses
- Maximum revision: 7 (plus 998/999 for variable formats)

**Error Codes:**
- Error 97: MID revision unsupported
- Error 09: Already subscribed (06 in some spec versions)

### Current Implementation (Lines 438-448)

```python
elif mid_int == 60: # MID 0060 Last tightening result data subscribe
    no_ack_flag = msg[11:12].decode('ascii')
    req_rev = int(rev) if rev.strip() else 1
    if req_rev > 1: resp = build_message(4, rev=1, data="006097") # Error: Revision
    elif self.result_subscribed: resp = build_message(4, rev=1, data="006009") # Error: Subscribed
    else:
        self.result_subscribed = True; self.result_no_ack = (no_ack_flag == "1")
        resp = build_message(5, rev=1, data="0060") # Accept
        print("[Tightening] Result subscription accepted.")
    self.send_to_client(resp)
    return
```

### Deviations Found

| ID | Field/Feature | Spec | Current | Severity | Notes |
|----|--------------|------|---------|----------|-------|
| 0060-D1 | Revision support | Rev 1-7 supported | Only Rev 1 accepted | **Major** | Limits integrator compatibility |
| 0060-D2 | Error code format | 4-digit MID + 2-digit error | "006097" (6 chars) | Minor | Format appears correct |
| 0060-D3 | Subscribed revision not stored | Should remember requested rev | Only stores subscription flag | **Major** | Can't send correct MID 0061 rev |
| 0060-D4 | NoAck flag handling | Byte position 11 (0-indexed) | Correct extraction | OK | Working correctly |

### Severity Assessment

- **Critical:** 0
- **Major:** 2 (D1, D3)
- **Minor:** 0
- **OK:** 2 (D2, D4)

### Recommendations

1. **D1/D3:** Store requested revision and use it when generating MID 0061 responses
2. Support at minimum revision 1-2 (same field structure), ideally up to revision 7

---

## MID 0061 - Last Tightening Result Data (Fields 01-11)

### Spec Reference
Open Protocol R2.8.0, Table 76 - MID 0061 Rev 1 field structure.

**Revision 1 Field Structure (23 total fields):**
```
Field 01: Cell ID - 4 digits
Field 02: Channel ID - 2 digits
Field 03: Controller name - 25 ASCII chars
Field 04: VIN number - 25 ASCII chars
Field 05: Job ID - 2 digits
Field 06: Parameter set ID - 3 digits
Field 07: Batch size - 4 digits
Field 08: Batch counter - 4 digits
Field 09: Tightening status - 1 digit (0=NOK, 1=OK)
Field 10: Torque status - 1 digit (0=Low, 1=OK, 2=High)
Field 11: Angle status - 1 digit (0=Low, 1=OK, 2=High)
```

**Message Header Format:**
- Length: 4 digits (calculated)
- MID: 0061
- Revision: 001 (for rev 1)
- NoAck: 0 or 1
- Station ID: 00
- Spindle ID: 00
- Spare: 4 spaces

### Current Implementation (Lines 544-558)

```python
params = {
    "01": f"{1:04d}", "02": f"{1:02d}", "03": self.controller_name,
    "04": self.current_vin.ljust(25), "05": f"{0:02d}",
    "06": (self.current_pset if self.current_pset else "0").rjust(3, '0'),
    "07": f"{current_target_batch_size:04d}",
    "08": f"{batch_counter_val:04d}",
    "09": status, "10": torque_status, "11": angle_status,
    ...
}
data = "".join([f"{pid}{pval}" for pid, pval in params.items()])
```

### Field-by-Field Audit (01-11)

| Field | Spec | Current Implementation | Status | Notes |
|-------|------|----------------------|--------|-------|
| 01 Cell ID | 4 digits, 2-char prefix "01" | `f"{1:04d}"` = "0001" | OK | Hardcoded to 1, format correct |
| 02 Channel ID | 2 digits, 2-char prefix "02" | `f"{1:02d}"` = "01" | OK | Hardcoded to 1, format correct |
| 03 Controller name | 25 chars, 2-char prefix "03" | `self.controller_name` (already ljust 25) | OK | Padded at initialization |
| 04 VIN | 25 chars, 2-char prefix "04" | `self.current_vin.ljust(25)` | **Minor** | Missing `[:25]` truncation |
| 05 Job ID | 2 digits, 2-char prefix "05" | `f"{0:02d}"` = "00" | OK | Hardcoded to 0, format correct |
| 06 Pset ID | 3 digits, 2-char prefix "06" | `.rjust(3, '0')` | OK | Zero-padded, correct |
| 07 Batch size | 4 digits, 2-char prefix "07" | `f"{...}:04d}"` | OK | Format correct |
| 08 Batch counter | 4 digits, 2-char prefix "08" | `f"{batch_counter_val:04d}"` | OK | Format correct |
| 09 Tightening status | 1 digit (0/1), 2-char prefix "09" | `status` (0 or 1) | OK | Values correct |
| 10 Torque status | 1 digit (0/1/2), 2-char prefix "10" | `torque_status` | OK | Values correct |
| 11 Angle status | 1 digit (0/1/2), 2-char prefix "11" | `angle_status` | OK | Values correct |

### Deviations Found (Fields 01-11)

| ID | Field/Feature | Spec | Current | Severity | Notes |
|----|--------------|------|---------|----------|-------|
| 0061-D1 | Field 04 VIN length | Exactly 25 chars | `.ljust(25)` without truncation | **Minor** | VINs >25 chars not truncated |
| 0061-D2 | Cell ID dynamic | Should be configurable | Hardcoded "0001" | **Minor** | Works but inflexible |
| 0061-D3 | Channel ID dynamic | Should be configurable | Hardcoded "01" | **Minor** | Works but inflexible |
| 0061-D4 | Job ID dynamic | Should be configurable | Hardcoded "00" | **Minor** | Works but inflexible |

### Message Header Audit

| Component | Spec | Current | Status | Notes |
|-----------|------|---------|--------|-------|
| Length calculation | Dynamic, matches content | `build_message()` handles | OK | Calculated correctly |
| MID field | "0061" | `mid=61` in build_message | OK | Formatted correctly |
| Revision field | "001" for rev 1 | `rev=1` | OK | Always sends rev 1 |
| NoAck flag | Stored from subscribe | `self.result_no_ack` | OK | Passed to build_message |
| Station ID | "00" | Hardcoded in build_message | OK | Default is correct |
| Spindle ID | "00" | Hardcoded in build_message | OK | Default is correct |

---

## MID 0061 - Last Tightening Result Data (Fields 12-23)

### Spec Reference
Open Protocol R2.8.0, Table 76 - MID 0061 Rev 1 field structure (continued).

**Revision 1 Field Structure (Fields 12-23):**
```
Field 12: Torque min limit - 6 digits (value x 100, e.g., 4700 = 47.00 Nm)
Field 13: Torque max limit - 6 digits (value x 100)
Field 14: Torque final target - 6 digits (value x 100)
Field 15: Torque - 6 digits (actual value x 100)
Field 16: Angle min - 5 digits (degrees)
Field 17: Angle max - 5 digits (degrees)
Field 18: Final angle target - 5 digits (degrees)
Field 19: Angle - 5 digits (actual degrees)
Field 20: Timestamp - 19 chars (YYYY-MM-DD:HH:MM:SS)
Field 21: Last change in parameter set - 19 chars (timestamp)
Field 22: Batch status - 1 digit (0=Not used, 1=OK, 2=NOK)
Field 23: Tightening ID - 10 digits
```

### Current Implementation (Lines 551-556)

```python
"12": f"{int(torque_min*100):06d}", "13": f"{int(torque_max*100):06d}",
"14": f"{int(target_torque*100):06d}", "15": f"{int(actual_torque*100):06d}",
"16": f"{int(angle_min):05d}", "17": f"{int(angle_max):05d}",
"18": f"{int(target_angle):05d}", "19": f"{int(actual_angle):05d}",
"20": timestamp_str, "21": pset_change_ts, "22": batch_status,
"23": tightening_id_str
```

### Field-by-Field Audit (12-23)

| Field | Spec | Current Implementation | Status | Notes |
|-------|------|----------------------|--------|-------|
| 12 Torque min | 6 digits x100, prefix "12" | `int(torque_min*100):06d` | OK | Scaling and format correct |
| 13 Torque max | 6 digits x100, prefix "13" | `int(torque_max*100):06d` | OK | Scaling and format correct |
| 14 Torque target | 6 digits x100, prefix "14" | `int(target_torque*100):06d` | OK | Scaling and format correct |
| 15 Torque actual | 6 digits x100, prefix "15" | `int(actual_torque*100):06d` | OK | Scaling and format correct |
| 16 Angle min | 5 digits, prefix "16" | `int(angle_min):05d` | OK | Format correct |
| 17 Angle max | 5 digits, prefix "17" | `int(angle_max):05d` | OK | Format correct |
| 18 Angle target | 5 digits, prefix "18" | `int(target_angle):05d` | OK | Format correct |
| 19 Angle actual | 5 digits, prefix "19" | `int(actual_angle):05d` | OK | Format correct |
| 20 Timestamp | 19 chars YYYY-MM-DD:HH:MM:SS | `strftime("%Y-%m-%d:%H:%M:%S")` | OK | Format matches spec exactly |
| 21 Pset change time | 19 chars timestamp | `pset_change_ts` | OK | Same format as field 20 |
| 22 Batch status | 1 digit (0/1/2) | `batch_status` | **Minor** | Value 2 (NOK) never generated |
| 23 Tightening ID | 10 digits | `f"{...}:04d"` (4 digits) | **Major** | Should be 10 digits, not 4 |

### Deviations Found (Fields 12-23)

| ID | Field/Feature | Spec | Current | Severity | Notes |
|----|--------------|------|---------|----------|-------|
| 0061-D5 | Field 23 Tightening ID | 10 digits | 4 digits (`{:04d}`) | **Major** | Field length incorrect |
| 0061-D6 | Field 22 Batch status | Values 0/1/2 | Only 0/1 used | **Minor** | Never generates batch NOK (2) |
| 0061-D7 | Torque scaling | Truncate (int) | Uses `int()` | OK | Matches spec (truncate, not round) |

### Scaling Factor Verification

| Field | Spec Scaling | Current | Result |
|-------|-------------|---------|--------|
| Torque fields (12-15) | x100 | `int(val*100)` | Correct |
| Angle fields (16-19) | None (raw degrees) | `int(val)` | Correct |

### Timestamp Format Verification

**Spec:** `YYYY-MM-DD:HH:MM:SS` (19 characters)
**Current:** `strftime("%Y-%m-%d:%H:%M:%S")`

Example output: `2026-01-16:14:30:45` (19 characters) - **Correct**

---

## MID 0062 - Last Tightening Result Acknowledge

### Spec Reference
Open Protocol R2.8.0 - MID 0062 is sent by integrator to acknowledge receipt of MID 0061.

**Per Specification:**
- Message format: Standard header only (no data fields)
- Sent by integrator after receiving MID 0061 (when NoAck=0)
- Controller expects this before sending next result (flow control)
- No error responses defined for MID 0062

### Current Implementation (Line 450)

```python
elif mid_int == 62: print("[Tightening] Tightening result acknowledged by client (MID 0062).")
```

### Deviations Found

| ID | Field/Feature | Spec | Current | Severity | Notes |
|----|--------------|------|---------|----------|-------|
| 0062-D1 | Flow control | Should wait for ack before next result | Results sent on timer regardless | **Minor** | Emulator behavior, not protocol error |

### Assessment
MID 0062 handling is minimal but acceptable for an emulator. The message is logged but doesn't block the next result from being sent. This is a design choice for emulator simplicity rather than a spec violation.

---

## MID 0063 - Last Tightening Result Unsubscribe

### Spec Reference
Open Protocol R2.8.0 - MID 0063 unsubscribes from tightening results.

**Per Specification:**
- Message format: Standard header only (no data fields)
- Response: MID 0005 (positive ack) with data "0063"
- Error code 10: Not subscribed

### Current Implementation (Lines 452-458)

```python
elif mid_int == 63: # MID 0063 Last tightening result unsubscribe
    if self.result_subscribed:
        self.result_subscribed = False; resp = build_message(5, rev=1, data="0063") # Accept
        print("[Tightening] Unsubscribed from tightening results.")
    else: resp = build_message(4, rev=1, data="006310") # Error: Not subscribed
    self.send_to_client(resp)
    return
```

### Deviations Found

| ID | Field/Feature | Spec | Current | Severity | Notes |
|----|--------------|------|---------|----------|-------|
| 0063-D1 | Error code 10 format | 4-digit MID + 2-digit error | "006310" | OK | Format correct |
| 0063-D2 | Positive ack format | MID 0005 with data "0063" | Correct | OK | Matches spec |

### Assessment
MID 0063 handling is correct. Error code 10 for "not subscribed" is properly returned.

---

## Audit Summary

### Deviation Counts by Severity

| MID | Critical | Major | Minor | Total |
|-----|----------|-------|-------|-------|
| 0060 | 0 | 2 | 0 | 2 |
| 0061 | 0 | 1 | 6 | 7 |
| 0062 | 0 | 0 | 1 | 1 |
| 0063 | 0 | 0 | 0 | 0 |
| **Total** | **0** | **3** | **7** | **10** |

### Prioritized Fix List

**Priority 1 - Major Deviations (Must Fix):**

| ID | MID | Issue | Fix |
|----|-----|-------|-----|
| 0060-D1 | 0060 | Only revision 1 accepted | Implement revision negotiation |
| 0060-D3 | 0060 | Subscribed revision not stored | Store requested revision for MID 0061 |
| 0061-D5 | 0061 | Tightening ID is 4 digits | Change to 10 digits (`{:010d}`) |

**Priority 2 - Minor Deviations (Should Fix):**

| ID | MID | Issue | Fix |
|----|-----|-------|-----|
| 0061-D1 | 0061 | VIN not truncated | Add `[:25]` truncation |
| 0061-D2/D3/D4 | 0061 | Hardcoded Cell/Channel/Job IDs | Make configurable (optional) |
| 0061-D6 | 0061 | Batch status 2 never used | Consider adding batch NOK logic |
| 0062-D1 | 0062 | No flow control | Consider ack-based send throttling |

### Impact Assessment

**Integrator Compatibility:**
- Revision 1 only support will cause issues with integrators expecting higher revisions
- Tightening ID length mismatch may cause parsing failures in strict integrators
- Overall: Medium impact, needs Phase 3 attention

**Protocol Compliance:**
- MID 0060-0063 are mostly compliant with revision 1 spec
- Major issue: Field 23 length deviation breaks the 167-byte expected message size
- Overall: Partial compliance (revision 1 only)

### Calculated MID 0061 Rev 1 Message Size

```
Header: 20 bytes (length 4 + MID 4 + rev 3 + noack 1 + station 2 + spindle 2 + spare 4)
Field prefixes: 23 fields x 2 chars = 46 bytes
Field 01 Cell ID: 4 bytes
Field 02 Channel ID: 2 bytes
Field 03 Controller name: 25 bytes
Field 04 VIN: 25 bytes
Field 05 Job ID: 2 bytes
Field 06 Pset ID: 3 bytes
Field 07 Batch size: 4 bytes
Field 08 Batch counter: 4 bytes
Field 09 Tightening status: 1 byte
Field 10 Torque status: 1 byte
Field 11 Angle status: 1 byte
Field 12-15 Torque values: 4 x 6 = 24 bytes
Field 16-19 Angle values: 4 x 5 = 20 bytes
Field 20-21 Timestamps: 2 x 19 = 38 bytes
Field 22 Batch status: 1 byte
Field 23 Tightening ID: 10 bytes (spec) / 4 bytes (current)

Spec total data: 155 bytes + 46 prefixes = 201 bytes
Current total data: 149 bytes + 46 prefixes = 195 bytes (6 bytes short)

Full message (spec): 20 + 201 + 1 (NUL) = 222 bytes
Full message (current): 20 + 195 + 1 (NUL) = 216 bytes
```

**Discrepancy:** Current implementation produces messages 6 bytes shorter than spec due to Tightening ID field.

