# Roadmap: Open Protocol Emulator - PF6000 Expansion

## Overview

Expand the existing Open Protocol emulator from a working but limited state to a spec-compliant, configurable PF6000 simulator. The journey starts by cleaning up technical debt, then auditing and fixing existing MID implementations against the official spec, followed by adding new MIDs, implementing revision configurability, and finally expanding the GUI.

## Domain Expertise

None

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Technical Debt Cleanup** - Fix duplicate method, bare excepts, prepare codebase for expansion
- [x] **Phase 2: MID Format Audit** - Audit all existing MID implementations against Open Protocol spec
- [x] **Phase 3: MID Format Fixes** - Fix spec deviations discovered during audit
- [x] **Phase 3.5: Architecture Refactor** - INSERTED: Refactor process_message() to registry-based dispatch
- [x] **Phase 4: Multi-Revision Implementation** - Implement revision 2+ response formats for all existing MIDs
- [ ] **Phase 5: New MID Implementation** - Implement MID 0082, 0100-0102, 0214-0218
- [ ] **Phase 6: Revision Configuration** - Add per-MID revision levels and controller profiles
- [ ] **Phase 7: GUI Expansion** - Add revision configuration controls to Tkinter interface

## Phase Details

### Phase 1: Technical Debt Cleanup
**Goal**: Clean codebase ready for safe expansion
**Depends on**: Nothing (first phase)
**Research**: Unlikely (internal refactoring using existing patterns)
**Plans**: TBD

Key work:
- Remove duplicate `_increment_vin()` method (lines 153-187)
- Replace bare `except:` clauses with specific exception handling (5 locations)
- Address thread safety concerns on shared state variables
- Consider dispatch pattern refactor for `process_message()` if beneficial

Plans:
- [x] 01-01: Fix duplicate method and bare except clauses
- [x] 01-02: Thread safety improvements for shared state

### Phase 2: MID Format Audit
**Goal**: Complete audit report of all MID implementations vs official spec
**Depends on**: Phase 1
**Research**: Likely (external specification validation)
**Research topics**: Open Protocol specification document for exact MID message formats, field lengths, revision differences
**Plans**: TBD

Key work:
- Audit MID 0001-0005 (communication start/stop, errors, ack)
- Audit MID 0014-0018 (parameter set selection)
- Audit MID 0042-0043 (tool enable/disable)
- Audit MID 0050-0054 (VIN handling)
- Audit MID 0060-0063 (tightening results)
- Audit MID 9999 (keep-alive)
- Document deviations with spec references

Plans:
- [x] 02-01: Audit communication and control MIDs (0001-0005, 0042-0043, 9999)
- [x] 02-02: Audit parameter and VIN MIDs (0014-0018, 0050-0054)
- [x] 02-03: Audit tightening result MIDs (0060-0063)

### Phase 3: MID Format Fixes
**Goal**: All existing MIDs match Open Protocol specification exactly
**Depends on**: Phase 2
**Research**: Unlikely (fixing based on audit results from Phase 2)

Key work:
- Fix MID 0015 format (add Date of Last Change field)
- Implement MID 0017 (parameter set unsubscribe)
- Add MID 0040/0041 notifications after tool control
- Fix MID 0061 tightening ID field length (4→10 digits)
- Fix VIN truncation in MID 0061

Plans:
- [x] 03-01: Fix parameter set MIDs (MID 0015 format, MID 0017, MID 0018 Pset 0)
- [x] 03-02: Fix tool control MIDs (MID 0040/0041 notifications)
- [x] 03-03: Fix tightening result MIDs (MID 0061 field lengths)

### Phase 3.5: Architecture Refactor (INSERTED)
**Goal**: Refactor process_message() from if/elif chain to registry-based dispatch
**Depends on**: Phase 3
**Research**: Unlikely (internal refactoring)

Key work:
- Create MID handler registry dictionary
- Extract each MID handler to dedicated method
- Reduce process_message() from ~200 lines to ~20 lines
- Standardize handler signature for consistency

Plans:
- [x] 03.5-01: Registry-based MID dispatch refactor

### Phase 4: Multi-Revision Implementation
**Goal**: All existing MIDs support multiple revisions per Open Protocol spec
**Depends on**: Phase 3.5
**Research**: Likely (revision-specific field differences from spec)
**Research topics**: Open Protocol specification for revision differences per MID - field additions, format changes, data length variations between revisions
**Plans**: TBD

Key work:
- Implement revision 2+ formats for MID 0001-0005 (communication)
- Implement revision 2+ formats for MID 0014-0018 (parameter sets)
- Implement revision 2+ formats for MID 0042-0043 (tool control)
- Implement revision 2+ formats for MID 0050-0054 (VIN handling)
- Implement revision 2+ formats for MID 0060-0063 (tightening results)
- Remove hardcoded `if requested_rev > 1: reject` patterns
- Add revision negotiation logic per Open Protocol spec

Plans:
- [x] 04-01: Multi-revision support for communication MIDs (0001-0005)
- [x] 04-02: Multi-revision support for parameter set MIDs (0014-0018)
- [x] 04-03: Multi-revision support for tool control MIDs (0040-0043)
- [x] 04-04: Multi-revision support for VIN MIDs (0050-0054)
- [x] 04-05: Multi-revision support for tightening result MIDs (0060-0063)

### Phase 5: New MID Implementation
**Goal**: Implement required new MIDs per spec
**Depends on**: Phase 3.5
**Research**: Likely (new MID specifications)
**Research topics**: MID 0082 set time format, MID 0100-0102 multi-spindle message structure, MID 0214-0218 I/O and relay formats
**Plans**: TBD

Key work:
- Implement MID 0082 - Set time
- Implement MID 0100-0102 - Multi-spindle controllers
- Implement MID 0214-0215 - I/O device status
- Implement MID 0216-0218 - Relay functions

Plans:
- [ ] 05-01: Implement MID 0082 (set time)
- [ ] 05-02: Implement MID 0100-0102 (multi-spindle)
- [ ] 05-03: Implement MID 0214-0218 (I/O and relay)

### Phase 6: Revision Configuration
**Goal**: Per-MID revision levels and controller profiles working
**Depends on**: Phase 5
**Research**: Unlikely (internal architecture, patterns established)
**Plans**: TBD

Key work:
- Design revision configuration data structure
- Implement per-MID revision level settings
- Create controller profiles (e.g., "PF6000 v1.8") that preset MID revisions
- Add profile save/load capability

Plans:
- [ ] 06-01: Per-MID revision configuration system
- [ ] 06-02: Controller profiles with presets

### Phase 7: GUI Expansion
**Goal**: Tkinter GUI controls for revision configuration
**Depends on**: Phase 6
**Research**: Unlikely (Tkinter patterns established in existing codebase)
**Plans**: TBD

Key work:
- Add revision configuration panel to GUI
- Add controller profile selection dropdown
- Add per-MID revision override controls
- Maintain existing GUI functionality

Plans:
- [ ] 07-01: Revision configuration GUI controls
- [ ] 07-02: Profile management UI

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 3.5 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Technical Debt Cleanup | 2/2 | Complete | 2026-01-16 |
| 2. MID Format Audit | 3/3 | Complete | 2026-01-16 |
| 3. MID Format Fixes | 3/3 | Complete | 2026-01-16 |
| 3.5. Architecture Refactor | 1/1 | Complete | 2026-01-16 |
| 4. Multi-Revision Implementation | 5/5 | Complete | 2026-01-16 |
| 5. New MID Implementation | 0/3 | Planned | - |
| 6. Revision Configuration | 0/2 | Not started | - |
| 7. GUI Expansion | 0/2 | Not started | - |
