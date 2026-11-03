# Avena Electrical v0.9.6 — COM read benchmark (experimental)

This is a diagnostic probe for version 0.9.6. It is **not** a new release, it does **not** patch the installed Windows service, and it does not edit the active DWG.

## Why this is needed

Live COM diagnostics recorded `<unknown>.Count` when reading an AutoCAD collection. A previous layer-filtered enumeration of 6,351 model-space objects took approximately 60–86 seconds even though the `Aisle` layer had only 8 matching entities. In the upstream backend, `entity_list` iterates `ModelSpace.Item(i)` and reads type/layer per object, causing many individual COM calls.

## Safe local steps

Use the Windows Python environment where `pywin32` is available. **Open a disposable copy of the test DWG** and make sure AutoCAD has no active command or modal dialog.

1. Run `python probe_com_v096.py --layer Aisle`. This attaches via `GetActiveObject` and reads document/ModelSpace counts without launching a new AutoCAD instance.
2. Only on the disposable DWG, optionally run `python probe_com_v096.py --layer Aisle --limit 20 --allow-transient-selection`. This creates and deletes a uniquely named temporary SelectionSet and returns matching handles.
3. Compare returned handles/count and elapsed time with the existing COM `entity_list` API. Check ModelSpace vs PaperSpace, blocks, hatches, WCS/OCS, and geometry consistency.
4. Run `python -m unittest -v test_com_fastpath` to execute fake-COM unit tests.

## Safety and limitations

- No DWG save, close, layer change, entity creation, or deletion commands are issued. A temporary SelectionSet is still a **document-side transient object**, hence it is opt-in and restricted to disposable test files.
- The module attempts late dispatch only when a wrapper raises `AttributeError` for `.Count`; genuine COM busy/RPC errors are not suppressed.
- Tests run on Linux using mocks; **real AutoCAD 2027 validation is outstanding**. This code is deliberately not wired into production `ComBackend`.
- The local agent source and installation path have not been verified; updating GitHub does not update the running Windows application.
- Original DWG and current Gateway remain unchanged.

## Release gate

Integrate a fast layer filter into v0.9.6 only after successful real-Windows latency and correctness tests, preserving on-screen approval for edits and an explicit rollback path.
