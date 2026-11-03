"""Apply idempotent Windows launcher fix to an extracted v0.9.3 Avena Electrical source."""
from pathlib import Path
import sys,re

root=Path(sys.argv[1]).resolve()
common=root/"scripts/windows_common.ps1"
run=root/"scripts/run_windows.ps1"
tests=root/"tests/test_windows_launcher.py"
assert all(p.is_file() for p in (common,run,tests,root/"RUN.bat",root/"BUILD_EXE.bat"))

s=common.read_text(encoding="utf-8")
start=s.index("    if (Test-AvenaVenv $exe) {",s.index("function Ensure-AvenaVenv"))
end=s.index("    if (Test-Path $venv) {",start)
replacement="""    # The venv's own Python already passed a version/x64/exit-code health check.
    # Comparing its stdout again is unreliable under Windows PowerShell 5.1,
    # and not required: a healthy venv can be reused regardless of global Python.
    if (Test-AvenaVenv $exe) {
        Write-Host '[AVENA] Reusing existing healthy .venv (no rebuild).' -ForegroundColor Green
        return $exe
    }
    # Only an actually broken venv is preserved and rebuilt, never deleted.
"""
s=s[:start]+replacement+s[end:]
assert "Could not inspect existing venv interpreter" not in s
common.write_text(s,encoding="utf-8")

s=run.read_text(encoding="utf-8")
needle="    & $Exe -c 'import fastmcp, ezdxf, pydantic, pythoncom, pytest, server'"
assert s.count(needle)==1
s=s.replace(needle,"    & $Exe -B (Join-Path $PSScriptRoot 'dependency_probe.py')")
run.write_text(s,encoding="utf-8")

(root/"scripts/dependency_probe.py").write_text('''"""Import required packages without PowerShell native -c quoting."""
from importlib import import_module
import sys
modules = ("fastmcp", "ezdxf", "pydantic", "pythoncom", "pytest", "server")
missing = []
for name in modules:
    try:
        import_module(name)
    except Exception as exc:
        missing.append(name + ": " + str(exc)[:90])
if missing:
    print("[AVENA] Missing/broken dependencies: " + "; ".join(missing))
    raise SystemExit(1)
print("[AVENA] Python dependencies healthy")
''',encoding="utf-8")

s=tests.read_text(encoding="utf-8")
start=s.index("def test_existing_venv_does_not_silently_keep_older_python():")
end=s.index("def test_windows_probe_uses_script_not_interpreter_c_strings():",start)
s=s[:start]+'''def test_existing_venv_reused_when_healthy_on_second_launch():
    common=(ROOT / "scripts" / "windows_common.ps1").read_text(encoding="utf-8")
    section=common.split("function Ensure-AvenaVenv",1)[1].split("function Ensure-AvenaSource",1)[0]
    assert "if (Test-AvenaVenv $exe)" in section
    assert "Reusing existing healthy .venv" in section
    assert "return $exe" in section
    assert "Could not inspect existing venv interpreter" not in section
    assert "currentFamily" not in section
    assert "venvFamily" not in section
    for entry in ("scripts/run_windows.ps1", "scripts/build_windows.ps1"):
        script=(ROOT / entry).read_text(encoding="utf-8")
        assert "$Exe = Ensure-AvenaVenv $Root $Selected" in script


'''+s[end:]
s=s.replace('assert "Reusing compatible virtual environment" in common',
            'assert "Reusing existing healthy .venv" in common')
s+='''

def test_run_dependency_probe_is_file_based_not_inline_code():
    script=(ROOT / "scripts" / "run_windows.ps1").read_text(encoding="utf-8")
    assert "dependency_probe.py" in script
    assert "& $Exe -c" not in script
    probe=(ROOT / "scripts" / "dependency_probe.py").read_text(encoding="utf-8")
    assert "import_module(name)" in probe


def test_version_repeated_interpreter_does_not_force_venv_rebuild():
    common=(ROOT / "scripts" / "windows_common.ps1").read_text(encoding="utf-8")
    section=common.split("function Ensure-AvenaVenv",1)[1].split("function Ensure-AvenaSource",1)[0]
    happy=section.index("if (Test-AvenaVenv $exe)")
    reuse=section.index("return $exe",happy)
    preserve=section.index("Move-Item -LiteralPath $venv",reuse)
    assert happy < reuse < preserve
'''
tests.write_text(s,encoding="utf-8")

(root/"scripts/test_launcher_twice.ps1").write_text('''$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "windows_common.ps1")
$Addon = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Root = Join-Path $Addon ".build"
try {
    $selected = Ensure-AvenaPython
    $first = Ensure-AvenaVenv $Root $selected
    $second = Ensure-AvenaVenv $Root $selected
    if ($first -ne $second) { throw "Venv path changed on second launch" }
    if (-not (Test-AvenaVenv $second)) { throw "Venv health check failed" }
    Write-Host "[PASS] First and second launcher checks succeeded; same .venv reused." -ForegroundColor Green
} catch {
    Write-Host "[FAIL] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
''',encoding="utf-8")
(root/"TEST_LAUNCHER_TWICE.bat").write_text('''@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\\test_launcher_twice.ps1"
set "STATUS=%ERRORLEVEL%"
if "%STATUS%"=="0" (echo [AVENA] Both simulated launches succeeded.) else (echo [AVENA] Launcher validation failed.)
pause
exit /b %STATUS%
''',encoding="utf-8")
init=root/"app/__init__.py"
v=init.read_text(encoding="utf-8")
if '__version__ = "0.9.3"' not in v:raise RuntimeError("Expected 0.9.3 base")
init.write_text(v.replace('__version__ = "0.9.3"','__version__ = "0.9.4"'),encoding="utf-8")
(root/"README_V094_FA.txt").write_text('''Avena Electrical v0.9.4 — Windows x64, Python 3.11+
Fix RUN.bat and BUILD_EXE.bat when executed again after first successful run.
A previously working .build/.venv is reused based on its own interpreter health check.
No second fragile PowerShell stdout version comparison.
A broken .venv is renamed and preserved; a new one is created.
RUN Python dependency detection now uses a separate Python script, no -c quoting.
Run TEST_LAUNCHER_TWICE.bat to verify two venv initializations on Windows.
All v0.9.3 online license, light/dark GUI, cloud agent, drawing/editing features remain.
This ZIP is full source + bundled pinned engine, NOT a precompiled Windows EXE.
''',encoding="utf-8")
print("LAUNCHER_V094_PATCHED",root)
