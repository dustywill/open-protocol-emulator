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

