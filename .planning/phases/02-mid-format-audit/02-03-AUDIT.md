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

