"""Build Avena Electrical v0.9.5 with robust Windows PyPI fallback installer."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import re,sys,hashlib

old=Path(sys.argv[1]);dest=Path(sys.argv[2]);work=Path(sys.argv[3])
with ZipFile(old) as z:
 if z.testzip():raise RuntimeError("Base ZIP corrupt")
 z.extractall(work)
roots=[p for p in work.iterdir() if p.is_dir()]
assert len(roots)==1
root=roots[0]
root.rename(root.with_name("AvenaElectrical-v0.9.5-Complete-Windows"))
root=root.with_name("AvenaElectrical-v0.9.5-Complete-Windows")
common=root/"scripts/windows_common.ps1"
s=common.read_text(encoding="utf-8")
assert "function Ensure-AvenaVenv" in s and "function Install-AvenaDependencies" not in s
s+='''
# Always select an explicit HTTPS index. A preconfigured pip mirror can be
# stale, especially when FastMCP adds a recent Authlib dependency.
function Install-AvenaDependencies([string]$PythonExe, [string]$Repo, [bool]$ForBuild) {
    $indexes = @(
        'https://pypi.org/simple/',
        'https://mirrors.aliyun.com/pypi/simple/',
        'https://pypi.tuna.tsinghua.edu.cn/simple/'
    )
    if (-not [string]::IsNullOrWhiteSpace($env:AVENA_PIP_INDEX_URL)) {
        $preferred = $env:AVENA_PIP_INDEX_URL.Trim()
        if ($preferred -notmatch '^https://[a-zA-Z0-9.-]+(?::443)?/[^\\s]*$') {
            throw 'AVENA_PIP_INDEX_URL must be an HTTPS PyPI-compatible index URL.'
        }
        $indexes = @($preferred) + @($indexes | Where-Object { $_ -ne $preferred })
    }
    $requirements = @('-e', ($Repo + '[full]'), 'pytest')
    if ($ForBuild) { $requirements += 'pyinstaller' }
    # Avoid accidental disabled-network mode and untrusted supplementary indexes.
    $priorNoIndex = $env:PIP_NO_INDEX
    $priorExtraIndex = $env:PIP_EXTRA_INDEX_URL
    try {
        Remove-Item Env:PIP_NO_INDEX -ErrorAction SilentlyContinue
        Remove-Item Env:PIP_EXTRA_INDEX_URL -ErrorAction SilentlyContinue
        foreach ($index in $indexes) {
            Write-Host "[AVENA] Installing Python dependencies from $index" -ForegroundColor Cyan
            $argsForPip = @('-m','pip','install','--disable-pip-version-check',
                '--prefer-binary','--timeout','35','--retries','2',
                '--index-url', $index) + $requirements
            & $PythonExe @argsForPip
            if ($LASTEXITCODE -eq 0) {
                $probe = if ($ForBuild) { 'build_dependency_probe.py' } else { 'dependency_probe.py' }
                & $PythonExe -B (Join-Path $PSScriptRoot $probe)
                if ($LASTEXITCODE -eq 0) {
                    Write-Host '[AVENA] Dependencies are installed and verified.' -ForegroundColor Green
                    return
                }
            }
            Write-Host "[AVENA] Package source failed; trying next trusted HTTPS index." -ForegroundColor Yellow
        }
    } finally {
        if ($null -eq $priorNoIndex) {
            Remove-Item Env:PIP_NO_INDEX -ErrorAction SilentlyContinue
        } else { $env:PIP_NO_INDEX = $priorNoIndex }
        if ($null -eq $priorExtraIndex) {
            Remove-Item Env:PIP_EXTRA_INDEX_URL -ErrorAction SilentlyContinue
        } else { $env:PIP_EXTRA_INDEX_URL = $priorExtraIndex }
    }
    throw 'Python dependencies unavailable from all configured indexes. Check TLS, DNS, firewall or proxy. Read pip output above; no downgrade or deletion performed.'
}
'''
common.write_text(s,encoding="utf-8")
run=root/"scripts/run_windows.ps1"
s=run.read_text(encoding="utf-8")
oldrun='''        & $Exe -m pip install -e "${Repo}[full]" pytest
        if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed (PyPI/network error).' }'''
assert oldrun in s
s=s.replace(oldrun,'        Install-AvenaDependencies $Exe $Repo $false')
run.write_text(s,encoding="utf-8")
build=root/"scripts/build_windows.ps1"
s=build.read_text(encoding="utf-8")
oldbuild='''    & $Exe -m pip install -e "${Repo}[full]" pyinstaller pytest
    if ($LASTEXITCODE -ne 0) { throw 'Could not install build dependencies.' }'''
assert oldbuild in s
s=s.replace(oldbuild,'''    & $Exe -B (Join-Path $PSScriptRoot 'build_dependency_probe.py')
    if ($LASTEXITCODE -ne 0) {
        Install-AvenaDependencies $Exe $Repo $true
    } else {
        Write-Host '[AVENA] Build dependencies already installed; skipping pip.' -ForegroundColor Green
    }''')
build.write_text(s,encoding="utf-8")

(root/"scripts/build_dependency_probe.py").write_text('''"""Verify PyInstaller and AutoCAD runtime imports before reinstalling."""
from importlib import import_module
import sys
for name in ("fastmcp","ezdxf","pydantic","pythoncom","pytest","server","PyInstaller"):
    try:
        import_module(name)
    except Exception as exc:
        print("[AVENA] Needs dependency: %s (%s)" % (name,str(exc)[:120]))
        raise SystemExit(1)
print("[AVENA] All build dependencies are available")
''',encoding="utf-8")

tests=root/"tests/test_windows_launcher.py"
s=tests.read_text(encoding="utf-8")
s+='''

def test_package_install_has_explicit_healthy_indexes():
    common=(ROOT / "scripts/windows_common.ps1").read_text(encoding="utf-8")
    assert "function Install-AvenaDependencies" in common
    assert "https://pypi.org/simple/" in common
    assert "https://mirrors.aliyun.com/pypi/simple/" in common
    assert "https://pypi.tuna.tsinghua.edu.cn/simple/" in common
    assert "--index-url" in common
    assert "PIP_EXTRA_INDEX_URL" in common
    assert "AVENA_PIP_INDEX_URL" in common

def test_run_and_build_share_recovery_logic():
    run=(ROOT / "scripts/run_windows.ps1").read_text(encoding="utf-8")
    build=(ROOT / "scripts/build_windows.ps1").read_text(encoding="utf-8")
    assert "Install-AvenaDependencies $Exe $Repo $false" in run
    assert "Install-AvenaDependencies $Exe $Repo $true" in build
    assert "build_dependency_probe.py" in build
    assert "-m pip install -e" not in run
    assert "-m pip install -e" not in build

def test_build_dependency_probe_is_valid():
    from pathlib import Path
    probe=(ROOT / "scripts/build_dependency_probe.py").read_text(encoding="utf-8")
    compile(probe,"build_dependency_probe.py","exec")
    assert '"PyInstaller"' in probe
    assert '"pythoncom"' in probe
'''
tests.write_text(s,encoding="utf-8")
init=root/"app/__init__.py"
s=init.read_text(encoding="utf-8")
assert '__version__ = "0.9.4"' in s
init.write_text(s.replace('__version__ = "0.9.4"','__version__ = "0.9.5"'),encoding="utf-8")
(root/"README_V095_FA.txt").write_text('''Avena Electrical v0.9.5 / Windows x64 / Python 3.11+.
Full source with bundled CAD engine.
Fixed pip install failing on stale indexes missing authlib>=1.6.11.
Uses official PyPI explicitly; HTTPS mirrors are automatic fallbacks.
Use AVENA_PIP_INDEX_URL (HTTPS only) to prefer a custom trusted index.
RUN.bat / BUILD_EXE.bat reuse installed healthy dependencies before pip.
DO NOT delete the .build directory or DPAPI device license.
TEST_LAUNCHER_TWICE.bat tests virtualenv reuse without launching AutoCAD.
The executable is created with BUILD_EXE.bat; ZIP itself is source, not EXE.
''',encoding="utf-8")
for py in root.rglob("*.py"):
 if any(x in py.parts for x in ("__pycache__",".build")):continue
 compile(py.read_bytes(),str(py),"exec")
excludes={".build","__pycache__",".venv",".pytest_cache","dist",".git"}
with ZipFile(dest,"w",ZIP_DEFLATED,compresslevel=8) as z:
 for p in root.rglob("*"):
  if p.is_file() and not any(part in excludes for part in p.relative_to(root).parts) and p.suffix not in (".pyc",".pyo"):
   z.write(p,str(root.name+"/"+str(p.relative_to(root))))
with ZipFile(dest) as z:
 assert z.testzip() is None
 print("RELEASE_095",len(z.namelist()),dest.stat().st_size,hashlib.sha256(dest.read_bytes()).hexdigest())
