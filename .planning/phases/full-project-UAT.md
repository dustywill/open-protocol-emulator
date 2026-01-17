---
status: testing
phase: full-project
source: [03-01-SUMMARY.md through 06-02-SUMMARY.md]
started: 2026-01-17T00:00:00Z
updated: 2026-01-17T00:00:00Z
---

## Current Test

number: 1
name: Basic Connection (MID 0001/0002)
expected: |
  Send MID 0001 rev 1 to emulator. Receive MID 0002 rev 1 response with 20-byte Cell ID.
  For rev 6: Response should include Cell ID, Channel ID, Controller Name, Supplier Code, Open Protocol Version, Controller Software Version, Tool Software Version, RBU Type, Controller Serial Number, System Type, System Sub Type.
awaiting: user response

## Tests

### 1. Basic Connection (MID 0001/0002)
expected: Send MID 0001 rev 1. Receive MID 0002 rev 1 with 20-byte Cell ID. Rev 6 includes all extended fields.
result: [pending]

### 2. Revision Negotiation
expected: Send MID 0001 rev 99. Emulator should respond with MID 0002 at max supported revision (6), not reject.
result: [pending]

### 3. MID 0015 Pset Selection Response
expected: Subscribe to Pset (MID 0014). Response MID 0015 should have 22-byte data: 3-digit Pset ID + 19-byte Date of Last Change (YYYY-MM-DD:HH:MM:SS).
result: [pending]

### 4. MID 0017 Pset Unsubscribe
expected: Send MID 0017 (unsubscribe Pset). Should receive MID 0005 acknowledgment. Subsequent Pset changes should NOT send notifications.
result: [pending]

### 5. MID 0018 Pset 0 Selection
expected: Send MID 0018 with Pset ID "000". Should receive MID 0005 ack + MID 0015 notification for Pset 0 (no parameter set selected).
result: [pending]

### 6. Tool Disable Notification (MID 0042)
expected: Send MID 0042 (disable tool request). Should receive MID 0005 ack followed by MID 0040 notification (header only, no data).
result: [pending]

### 7. Tool Enable Notification (MID 0043)
expected: Send MID 0043 (enable tool request). Should receive MID 0005 ack followed by MID 0041 notification (header only, no data).
result: [pending]

### 8. MID 0061 Tightening ID (10 digits)
expected: Trigger a tightening result. Field 23 (Tightening ID) should be exactly 10 digits, zero-padded (e.g., "0000000001").
result: [pending]

### 9. MID 0061 VIN Field (25 chars)
expected: Set a VIN longer than 25 chars, trigger tightening. MID 0061 Field 04 (VIN) should be exactly 25 characters (truncated if needed).
result: [pending]

### 10. MID 0041 Tool Data (Multi-Rev)
expected: Send MID 0040 rev 1-5. MID 0041 response should include fields based on revision (rev 5 includes all: serial, calibration, service dates, counters, specs).
result: [pending]

### 11. MID 0052 VIN Response (Rev 1 vs 2)
expected: Subscribe MID 0051 rev 1: MID 0052 returns 25-char VIN only. Subscribe MID 0051 rev 2: MID 0052 returns 4-part identifier with field prefixes.
result: [pending]

### 12. MID 0061 Extended Fields (Rev 3-7)
expected: Subscribe MID 0060 rev 7. Tightening results include Fields 24-27: strategy code, strategy options, error status 2, stage result count.
result: [pending]

### 13. MID 0082 Set Time (Valid)
expected: Send MID 0082 with "2026-01-17:12:30:45". Should receive MID 0005 acknowledgment. Controller time is updated.
result: [pending]

### 14. MID 0082 Set Time (Invalid)
expected: Send MID 0082 with invalid format (wrong length or format). Should receive MID 0004 error with error code 20.
result: [pending]

### 15. Multi-Spindle Subscribe (MID 0100)
expected: Send MID 0100 rev 1-5. Should receive MID 0005 ack. Emulator ready to send MID 0101 results.
result: [pending]

### 16. Multi-Spindle Result (MID 0101)
expected: Trigger multi-spindle result. MID 0101 should contain spindle data: 18 bytes per spindle (num, channel, status, torque, angle).
result: [pending]

### 17. Multi-Spindle Unsubscribe (MID 0103)
expected: Send MID 0103 to unsubscribe. Should receive MID 0005 ack. No more MID 0101 results sent.
result: [pending]

### 18. I/O Device Status (MID 0214/0215)
expected: Send MID 0214 rev 1. Should receive MID 0215 with 8 digital inputs + 8 digital outputs. Rev 2 uses variable count format.
result: [pending]

### 19. Relay Subscribe (MID 0216)
expected: Send MID 0216 with relay function number. Should receive MID 0005 ack immediately followed by MID 0217 with current relay status.
result: [pending]

### 20. Relay Unsubscribe (MID 0219)
expected: Send MID 0219 for subscribed relay. Should receive MID 0005 ack. No more MID 0217 notifications for that relay.
result: [pending]

### 21. Revision Config API (get_max_revision)
expected: Call emulator.get_max_revision(2) to get MID 0002 max revision. Should return integer (default: 6).
result: [pending]

### 22. Revision Config API (set_max_revision)
expected: Call emulator.set_max_revision(2, 3). Subsequent MID 0001 requests should be limited to rev 3 max response.
result: [pending]

### 23. Profile: Apply Legacy
expected: Call emulator.apply_profile("legacy"). All MIDs should respond with revision 1 only.
result: [pending]

### 24. Profile: Apply PF6000-Full
expected: Call emulator.apply_profile("pf6000-full"). MIDs should respond with maximum supported revisions (6, 7, 5, 2, 5, 2).
result: [pending]

### 25. Profile: Get Available
expected: Call emulator.get_available_profiles(). Should return ["legacy", "pf6000-basic", "pf6000-full"].
result: [pending]

### 26. Profile: Save to JSON
expected: Call emulator.save_profile_to_file("test.json"). File should contain JSON with name, description, and revisions dict.
result: [pending]

### 27. Profile: Load from JSON
expected: Load a JSON profile file. Emulator revision config should update to match loaded profile.
result: [pending]

### 28. Error Response (MID 0004)
expected: Send invalid MID or invalid data. Should receive MID 0004 with appropriate error code (matches spec error codes).
result: [pending]

## Summary

total: 28
passed: 0
issues: 0
pending: 28
skipped: 0

## Gaps

[none yet]
