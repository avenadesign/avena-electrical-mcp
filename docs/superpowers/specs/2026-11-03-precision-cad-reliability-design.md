# Avena Electrical — Precision CAD reliability audit (2026-11-03)

## Scope and intent
Use Superpowers-style root-cause investigation, test-driven fixes, and fresh verification to safely analyze the current Windows AutoCAD document through Avena Electrical. Never silently change, delete, open, save, or close the user's DWG.

## Verified findings
- Active AutoCAD: 2027 via COM, one active DWG, 6,351 entities, 51 layers, 190 block definitions.
- Engine reports 256 internal tools. The gated Avena cloud MCP catalog exposes 49 total tools, of which 40 are advanced inspection/viewport tools. The ChatGPT connector schema cached in the current conversation still advertises only 7 legacy tools.
- Windows device pairing: consistent connection_id c0753594; the cloud agent is live.
- Before the relay fix: server interpreted an Agent busy executing CAD for >35 seconds as offline; a 45-second RPC timeout could reject late results with HTTP 403. Root cause verified in source and access logs.
- Relay fix commit 5dde4f1a814276532b39352869228125cdc6f139. Regression commit d2a9193a8422bc31ca64e951989269a8e6b401dd. Eight tests passed, including no stale queued drawings being dispatched, response of agent_busy under concurrent load, offline detection, late result acknowledgement, read-only RPC round-trip and rejection of unrestricted commands.
- Live test after deployment: system_capabilities returned via real Windows COM in 1.09 s, confirming a v0.9.6 advanced tool works end-to-end.
- Live geometry: autocad_entity_list(layer_filter="Aisle", limit=8, offset=0) completed in 60.16 s and returned 8 entities (4 closed polylines plus 4 hatches), including real WCS coordinates/bounds. Handle 20793 was read directly in 0.86 s.
- Live units: INSUNITS=1 (inches declared). Do not interpret this as physical scale verification.
- COM selection_filter(layer="Aisle") timed out in 60.85 s with a warning of an uncancellable COM worker. Do not retry blindly; ensure AutoCAD has no open modal/active command. No drawing modifications were requested or made.
- Agent remained Online during the long layer enumeration, and a simultaneous second read returned agent_busy promptly after deployment.

## Architecture and safety boundaries
- Layer 1: OAuth + immutable phone/device license identity. No license rotation.
- Layer 2: Avena MCP relay: explicit read-only catalog, exact argument schemas, no arbitrary AutoLISP/commands/files; edits require local Windows approval.
- Layer 3: Windows cloud Agent: validate read arguments again, hold local MCP token inside per-user app, constrain Windows allowed document path on every write.
- Layer 4: Local FastMCP / AutoCAD COM: document-scoped WCS geometry, accurate handle/properties; no blind retries of mutating calls.
- Never equate a CAD layer named Aisle with a verified corridor; inspect architectural walls, doors, dimension references and viewport screenshots first.

## Next workstream: fast, reliable geometry queries
1. Benchmark and test *one* read-only fast path on a copy/test DWG: native AutoCAD selection set using layer filters, or a temporary DXF snapshot parsed with ezdxf. Do not switch the default engine based solely on conceptual correctness.
2. Compare handles, entity counts and geometry with the existing COM path; verify blocked/anonymous entities, nested block transforms, hatches, paper vs model space, WCS vs UCS and stale selections. Report skipped entities and source fidelity, not just totals.
3. Add TDD regressions before modifying upstream code. RED: 6,351-entity layer queries should complete comfortably below the present 60-second COM limit, with correct counts and geometry. GREEN on a real AutoCAD 2027 Windows seat is required before declaring success.
4. Record AutoCAD busy states, COM call duration and exact failure code in Windows logs without leaking activation keys or DWG data. Retry only provably idempotent reads, and never after a mutating call has unknown outcome.
5. Build a navigable engineering workflow: snapshot/inspect → verify units/scale → identify wall/door/corridor geometry with confidence → simulate CCTV coverage and occlusion → generate a per-camera proposal → preview → local approval → audit drawing diff. Maintain manual save and transaction/Undo discipline.
6. Refresh the ChatGPT connector schema so newly exposed tools become callable natively instead of only through diagnostics. Do not imply that publishing a new server-side tool automatically refreshes existing plugin installations.

## Release gates
- Full automated suite passes; no success claims from partial tests alone.
- Real Windows AutoCAD 2027: successful repeated launch, multiple successive read calls, large drawing performance benchmark, viewport screenshots, and reconciliation of geometry counts.
- DWG write tests only on an explicitly saved disposable test file, always with on-screen approval; verify Undo and no automatic save.
- Current production DWG must remain unchanged unless the user directly approves a specific camera-placement preview.
