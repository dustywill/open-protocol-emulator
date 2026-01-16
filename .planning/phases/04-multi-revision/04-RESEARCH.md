# Phase 4: Multi-Revision Implementation - Research

**Researched:** 2026-01-16
**Domain:** Open Protocol MID message format revisions
**Confidence:** HIGH
**Source:** Open Protocol Specification R2.8.0 (OpenProtocolSpecification_R280.txt)

<research_summary>
## Summary

Researched the Open Protocol specification for all MIDs currently implemented in the emulator and those planned for Phase 5. The specification defines multiple revisions for most MIDs, with each revision adding fields to the message format. The current emulator only supports revision 1 and explicitly rejects revision 2+ requests with error code 97.

Key finding: Revisions are additive - revision 2 includes all revision 1 fields plus additional fields. The controller should respond with the highest revision it supports that is ≤ the requested revision. If the integrator requests revision 3 and the controller only supports revision 2, it should respond with revision 2, not reject.

**Primary recommendation:** Implement revision support incrementally by MID group, starting with the most commonly used MIDs (communication, VIN, tightening results). Each MID handler needs revision-aware response building that selects appropriate field sets based on the requested revision.
</research_summary>

<standard_stack>
## Standard Stack

No external libraries required - this is pure protocol implementation using the existing codebase patterns.

### Core Technologies
| Technology | Purpose | Notes |
|-----------|---------|-------|
| Python 3 | Runtime | Already in use |
| ASCII encoding | Message format | Per Open Protocol spec |
| TCP/IP | Transport | Already implemented |

### Key Concepts
| Concept | Description |
|---------|-------------|
| Revision negotiation | Integrator requests revision X, controller responds with revision ≤ X it supports |
| Field numbering | Each field has a 2-digit prefix (01, 02, 03...) in the data portion |
| Additive revisions | Higher revisions include all lower revision fields plus new ones |
| Message length | Must be recalculated based on actual data field content |
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Current Pattern (Revision 1 Only)
```python
# Current: Hardcoded rejection of revision > 1
if requested_rev > 1:
    resp = build_message(4, rev=1, data="000197")  # Error: MID revision unsupported
```

### Recommended Pattern: Revision-Aware Handlers
```python
# Pattern 1: Revision dispatch within handler
def handle_mid_0001(self, requested_rev: int, data_field: str):
    supported_rev = min(requested_rev, self.MAX_REV_0001)

    if supported_rev == 1:
        return self._build_mid0002_rev1()
    elif supported_rev == 2:
        return self._build_mid0002_rev2()
    elif supported_rev == 3:
        return self._build_mid0002_rev3()

# Pattern 2: Field accumulation (cleaner for additive revisions)
def _build_mid0061(self, revision: int) -> str:
    fields = []

    # Revision 1 fields (always included)
    fields.append(f"01{self.cell_id:04d}")
    fields.append(f"02{self.channel_id:02d}")
    fields.append(f"03{self.controller_name:25s}")
    # ... more rev 1 fields

    if revision >= 2:
        fields.append(f"24{self.strategy_code:04d}")
        fields.append(f"25{self.strategy_options}")

    if revision >= 3:
        fields.append(f"26{self.step_results}")

    return "".join(fields)
```

### Recommended Project Structure Addition
```
open_protocol_emulator.py
├── Existing code
└── New additions:
    ├── MID revision constants (MAX_REV_XXXX)
    ├── Revision-aware field builders per MID
    └── Response revision calculation logic
```

### Anti-Patterns to Avoid
- **Separate handlers per revision:** Creates duplication; use field accumulation instead
- **Ignoring requested revision:** Must respond with correct revision in header
- **Hardcoded field positions:** Use named constants for byte offsets
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Message length calculation | Manual counting | `build_message()` function | Already handles length header correctly |
| ASCII padding | Custom string formatting | Python f-strings with width specifiers | `f"{value:06d}"` handles zero-padding |
| Field numbering | Hardcoded strings | Constants or formatted strings | Reduces errors, improves readability |
| Timestamp formatting | Custom datetime code | `datetime.strftime()` | Already correct format in spec |

**Key insight:** The existing `build_message()` helper should be extended to accept revision parameter and adjust accordingly. Don't create parallel message construction logic.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Response Revision Mismatch
**What goes wrong:** Integrator requests revision 2, controller sends revision 1 format but puts "002" in revision field
**Why it happens:** Not matching the response format to the revision number in header
**How to avoid:** Always build response data matching the revision number in the header
**Warning signs:** Integrator parsing errors, field misalignment

### Pitfall 2: Incorrect Revision Negotiation
**What goes wrong:** Rejecting valid revision requests instead of downgrading
**Why it happens:** Using `!=` instead of `>` when checking revision support
**How to avoid:** Always respond with highest supported revision ≤ requested
**Warning signs:** Integrators getting unexpected MID 0004 errors

### Pitfall 3: Field Length Errors
**What goes wrong:** Message length header doesn't match actual content
**Why it happens:** Adding new fields without recalculating total length
**How to avoid:** Always use `build_message()` which calculates length dynamically
**Warning signs:** Message parsing failures, buffer overruns

### Pitfall 4: Missing Field Prefixes
**What goes wrong:** Data fields without 2-digit numeric prefixes (01, 02, etc.)
**Why it happens:** Forgetting that Open Protocol uses field numbering
**How to avoid:** All data fields must start with 2-digit field number
**Warning signs:** Field misalignment, incorrect parsing

### Pitfall 5: Decimal Truncation vs Rounding
**What goes wrong:** Torque/angle values slightly off
**Why it happens:** Spec says "truncated" but code uses rounding
**How to avoid:** Use `int(value * 100)` not `round(value * 100)`
**Warning signs:** Values differ from physical controller by ±1
</common_pitfalls>

<mid_revision_matrix>
## MID Revision Matrix

### Currently Implemented MIDs (Phase 4 Scope)

| MID | Name | Max Rev | Current | Rev 2 Adds | Rev 3+ Adds |
|-----|------|---------|---------|------------|-------------|
| 0001 | Comm start request | 8 | 1 | Extra data fields | Subscription handling options |
| 0002 | Comm start ack | 8 | 1 | OpenProtocol version, controller S/W version | More system info |
| 0003 | Comm stop | 1 | 1 | N/A | N/A |
| 0004 | Comm negative ack | 3 | 1 | MID of failed command | Rev 3: adds extra error text |
| 0005 | Comm positive ack | 1 | 1 | N/A | N/A |
| 0014 | Pset selected subscribe | 1 | 1 | N/A | N/A |
| 0015 | Pset selected | 2 | 1 | Batch size, batch counter, OK counter | N/A |
| 0016 | Pset selected ack | 1 | 1 | N/A | N/A |
| 0017 | Pset unsubscribe | 1 | 1 | N/A | N/A |
| 0018 | Select Pset | 1 | 1 | N/A | N/A |
| 0040 | Tool data request | 1 | 1 | N/A | N/A |
| 0041 | Tool data reply | 5 | 1 | Tool S/N, calibration | More tool info per rev |
| 0042 | Disable tool | 1 | 1 | N/A | N/A |
| 0043 | Enable tool | 1 | 1 | N/A | N/A |
| 0050 | VIN download | 1 | 1 | N/A | N/A |
| 0051 | VIN subscribe | 2 | 1 | 4-part identifier support | N/A |
| 0052 | VIN number | 2 | 1 | 4-part identifier (parts 2-4) | N/A |
| 0053 | VIN ack | 1 | 1 | N/A | N/A |
| 0054 | VIN unsubscribe | 1 | 1 | N/A | N/A |
| 0060 | Result subscribe | 7 | 1 | Selects which revision of 0061 | N/A |
| 0061 | Tightening result | 999 | 1 | Strategy data, step results | See detailed table below |
| 0062 | Result ack | 1 | 1 | N/A | N/A |
| 0063 | Result unsubscribe | 1 | 1 | N/A | N/A |
| 9999 | Keep alive | 1 | 1 | N/A | N/A |

### MID 0061 Revision Details (Most Complex)

| Rev | Total Fields | Key Additions |
|-----|--------------|---------------|
| 1 | 23 fields | Basic: cell, channel, VIN, job, pset, batch, torque, angle, timestamp |
| 2 | 23 fields | Same structure as rev 1 (clarifications only) |
| 3 | 24 fields | +Strategy code |
| 4 | 25 fields | +Strategy options |
| 5 | 26 fields | +Tightening error status 2 |
| 6 | 27 fields | +Stage result count (for multi-stage) |
| 7 | 28 fields | +Stage results detail |
| 998 | Variable | Variable data format (PIDs) |
| 999 | Light | Compact format |

### Planned New MIDs (Phase 5 - For Reference)

| MID | Name | Max Rev | Notes |
|-----|------|---------|-------|
| 0082 | Set time | 1 | Simple 19-char timestamp |
| 0100 | Multi-spindle subscribe | 5 | Rev 2+ adds rewind point |
| 0101 | Multi-spindle result | 5 | Complex: repeating spindle data |
| 0102 | Multi-spindle ack | 1 | Simple ack |
| 0214 | IO device request | 2 | Device number only |
| 0215 | IO device reply | 2 | Relay list, digital input list |
| 0216 | Relay subscribe | 1 | Simple |
| 0217 | Relay function | 1 | Relay number + status |
| 0218 | Relay ack | 1 | Simple ack |
</mid_revision_matrix>

<code_examples>
## Code Examples

### MID 0002 Communication Start Acknowledge - All Revisions
```python
# Source: Open Protocol Specification R2.8.0, Section 5.2.2

def _build_mid0002(self, revision: int) -> str:
    """Build MID 0002 response data for given revision."""
    fields = []

    # Revision 1 fields
    fields.append(f"01{self.cell_id:04d}")           # Cell ID: 4 digits
    fields.append(f"02{self.channel_id:02d}")        # Channel ID: 2 digits
    fields.append(f"{self.controller_name:25s}")     # Controller name: 25 chars (no field num)

    if revision >= 2:
        fields.append(f"04{self.supplier_code:03d}")      # Supplier code: 3 digits
        fields.append(f"05{self.op_version:19s}")         # Open Protocol version
        fields.append(f"06{self.ctrl_sw_version:19s}")    # Controller S/W version
        fields.append(f"07{self.tool_sw_version:19s}")    # Tool S/W version

    if revision >= 3:
        fields.append(f"08{self.rbu_type:24s}")           # RBU type
        fields.append(f"09{self.ctrl_serial:10s}")        # Controller serial

    if revision >= 4:
        fields.append(f"10{self.system_type:10s}")        # System type
        fields.append(f"11{self.system_subtype:10s}")     # System subtype

    if revision >= 5:
        fields.append(f"12{self.seq_num_support:01d}")    # Sequence number support
        fields.append(f"13{self.link_support:01d}")       # Linking support
        fields.append(f"14{self.station_id:10s}")         # Station ID
        fields.append(f"15{self.station_name:25s}")       # Station name

    if revision >= 6:
        fields.append(f"16{self.client_id:01d}")          # Client ID

    return "".join(fields)
```

### MID 0052 VIN Number - Revision Support
```python
# Source: Open Protocol Specification R2.8.0, Section 5.7.3

def _build_mid0052(self, revision: int) -> str:
    """Build MID 0052 VIN data for given revision."""
    if revision == 1:
        # Rev 1: Just VIN number, 25 chars
        return self.current_vin.ljust(25)[:25]

    elif revision >= 2:
        # Rev 2: 4-part identifier
        fields = []
        fields.append(f"01{self.current_vin.ljust(25)[:25]}")      # VIN (part 1)
        fields.append(f"02{self.identifier_part2.ljust(25)[:25]}") # Part 2
        fields.append(f"03{self.identifier_part3.ljust(25)[:25]}") # Part 3
        fields.append(f"04{self.identifier_part4.ljust(25)[:25]}") # Part 4
        return "".join(fields)
```

### MID 0061 Tightening Result - Revision 1 Structure
```python
# Source: Open Protocol Specification R2.8.0, Table 76

def _build_mid0061_rev1(self) -> str:
    """Build MID 0061 revision 1 tightening result."""
    fields = []

    fields.append(f"01{self.cell_id:04d}")                    # Cell ID
    fields.append(f"02{self.channel_id:02d}")                 # Channel ID
    fields.append(f"03{self.controller_name:25s}")            # Controller name
    fields.append(f"04{self.current_vin:25s}")                # VIN number
    fields.append(f"05{self.job_id:02d}")                     # Job ID
    fields.append(f"06{self.pset_id:03d}")                    # Parameter set ID
    fields.append(f"07{self.batch_size:04d}")                 # Batch size
    fields.append(f"08{self.batch_counter:04d}")              # Batch counter
    fields.append(f"09{self.tightening_status:01d}")          # Status (0=NOK, 1=OK)
    fields.append(f"10{self.torque_status:01d}")              # Torque status (0=Low,1=OK,2=High)
    fields.append(f"11{self.angle_status:01d}")               # Angle status
    fields.append(f"12{int(self.torque_min * 100):06d}")      # Torque min (x100)
    fields.append(f"13{int(self.torque_max * 100):06d}")      # Torque max (x100)
    fields.append(f"14{int(self.torque_target * 100):06d}")   # Torque target (x100)
    fields.append(f"15{int(self.torque_final * 100):06d}")    # Torque final (x100)
    fields.append(f"16{self.angle_min:05d}")                  # Angle min
    fields.append(f"17{self.angle_max:05d}")                  # Angle max
    fields.append(f"18{self.angle_target:05d}")               # Target angle
    fields.append(f"19{self.angle_final:05d}")                # Final angle
    fields.append(f"20{self.timestamp:19s}")                  # Timestamp YYYY-MM-DD:HH:MM:SS
    fields.append(f"21{self.pset_change_time:19s}")           # Pset last change time
    fields.append(f"22{self.batch_status:01d}")               # Batch status (0=NOK,1=OK,2=unused)
    fields.append(f"23{self.tightening_id:010d}")             # Tightening ID

    return "".join(fields)
```

### Revision Negotiation Logic
```python
# Source: Open Protocol Specification R2.8.0, Section 3

def get_response_revision(self, mid: int, requested_rev: int) -> int:
    """
    Determine which revision to use in response.
    Returns highest supported revision <= requested.
    """
    max_supported = {
        1: 6,    # MID 0001 -> MID 0002 supports up to rev 6
        14: 1,   # MID 0014 -> only rev 1
        51: 2,   # MID 0051 -> supports rev 1 and 2
        60: 7,   # MID 0060 -> controls MID 0061 revision
        # ... etc
    }

    max_rev = max_supported.get(mid, 1)
    return min(requested_rev, max_rev)
```
</code_examples>

<implementation_order>
## Recommended Implementation Order

### Phase 4 Plan Breakdown

**Plan 04-01: Communication MIDs (0001-0005)**
- MID 0001/0002: Add revision 2-6 support for comm start
- MID 0004: Add revision 2-3 for enhanced error info
- Estimated complexity: Medium

**Plan 04-02: Parameter Set MIDs (0014-0018)**
- MID 0015: Add revision 2 (batch info)
- Others: Already single-revision
- Estimated complexity: Low

**Plan 04-03: Tool Control MIDs (0040-0043)**
- MID 0041: Add revision 2-5 (tool details)
- MID 0042/0043: Single-revision, already done
- Estimated complexity: Medium

**Plan 04-04: VIN MIDs (0050-0054)**
- MID 0052: Add revision 2 (4-part identifier)
- Others: Single-revision
- Estimated complexity: Low

**Plan 04-05: Tightening Result MIDs (0060-0063)**
- MID 0061: Add revision 2-7 support (most complex)
- MID 0060: Controls which rev of 0061 is sent
- Estimated complexity: High

### Priority Order
1. **0060/0061** - Most commonly used, most value
2. **0001/0002** - Required for proper handshake
3. **0050-0054** - Common production use
4. **0014-0018** - Production control
5. **0040-0043** - Tool management
</implementation_order>

<open_questions>
## Open Questions

1. **Revision 998/999 for MID 0061**
   - What we know: These are variable/compact formats
   - What's unclear: Are these commonly used in PF6000 integrations?
   - Recommendation: Implement rev 1-7 first, add 998/999 if needed

2. **System-wide revision configuration**
   - What we know: Real controllers have configurable revision caps
   - What's unclear: Should this be per-MID or global?
   - Recommendation: Start with per-MID constants, add configuration in Phase 6

3. **Backward compatibility**
   - What we know: Some integrators expect rev 1 only behavior
   - What's unclear: Should we support a "legacy mode"?
   - Recommendation: Default to highest supported, add config option later
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- OpenProtocolSpecification_R280.txt (C:/Users/byron/Downloads/OP/) - Full specification
  - Section 5.2: Communication MIDs
  - Section 5.3: Parameter set MIDs
  - Section 5.6: Tool MIDs
  - Section 5.7: VIN MIDs
  - Section 5.8: Tightening result MIDs
  - Section 5.28: Keep alive MID 9999

### Secondary (MEDIUM confidence)
- OpenProtocol_Specification_R_2.16.0.txt - Older version for comparison
- GetFile.pdf/txt - Additional reference material

### Codebase Analysis
- open_protocol_emulator.py - Current implementation reviewed
  - Line 304-305: Hardcoded revision 1 rejection
  - Line 309-310: MID 0002 revision 1 only response
  - Line 195: MID 0052 revision 1 only
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: Open Protocol v2.8.0 ASCII message format
- Ecosystem: Python socket/threading (already in codebase)
- Patterns: Revision negotiation, additive field building
- Pitfalls: Field alignment, length calculation, revision mismatch

**Confidence breakdown:**
- MID format specifications: HIGH - from official spec
- Revision behavior: HIGH - clearly documented in spec
- Implementation patterns: MEDIUM - derived from spec requirements
- Priority order: MEDIUM - based on typical usage patterns

**Research date:** 2026-01-16
**Valid until:** Indefinite - Open Protocol spec is stable

---

*Phase: 04-multi-revision*
*Research completed: 2026-01-16*
*Ready for planning: yes*
</metadata>
