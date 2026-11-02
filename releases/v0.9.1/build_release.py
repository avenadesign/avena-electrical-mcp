"""Build Avena Electrical v0.9.1 from the verified v0.9 full-source archive."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import shutil, sys, tempfile

base=Path(sys.argv[1])
out=Path(sys.argv[2])
with tempfile.TemporaryDirectory(prefix="avena-v091-") as tmp:
    root=Path(tmp)
    with ZipFile(base) as z:
        if any(n.startswith("/") or ".." in Path(n).parts for n in z.namelist()):
            raise RuntimeError("Unsafe ZIP paths")
        z.extractall(root)
    folders=[x for x in root.iterdir() if x.is_dir()]
    if len(folders)!=1:raise RuntimeError("Expected one source folder")
    old=folders[0]
    new=old.with_name("AvenaElectrical-v0.9.1-Complete-Windows")
    old.rename(new)
    common=new/"scripts/windows_common.ps1"
    s=common.read_text(encoding="utf-8")
    signature="$AvenaPythonValidation = 'import sys; sys.exit(0 if (sys.version_info >= (3, 11) and sys.maxsize > 2**32) else 6)'"
    assert signature in s
    s=s.replace(signature,"$AvenaPythonValidation = Join-Path $PSScriptRoot 'python_probe.py'")
    assert "@('-c', $AvenaPythonValidation)" in s
    s=s.replace("@('-c', $AvenaPythonValidation)","@('-B', $AvenaPythonValidation)")
    assert "@('-c', 'import sys;print(sys.version_info[0],sys.version_info[1],sys.version_info[2])')" in s
    assert "@('-c', 'import sys;print(sys.version_info[0],sys.version_info[1])')" in s
    s=s.replace("@('-c', 'import sys;print(sys.version_info[0],sys.version_info[1],sys.version_info[2])')","@('-B', $AvenaPythonValidation)")
    s=s.replace("@('-c', 'import sys;print(sys.version_info[0],sys.version_info[1])')","@('-B', $AvenaPythonValidation)")
    assert "& $exe -c 'import sys;print(sys.version_info[0],sys.version_info[1])'" in s
    s=s.replace("& $exe -c 'import sys;print(sys.version_info[0],sys.version_info[1])'","& $exe -B $AvenaPythonValidation")
    oldblock='''        if (([string]$currentFamily).Trim() -ne ([string]$venvFamily).Trim()) {
            throw "Installed Python is $currentFamily but .build\\.venv uses $venvFamily. To use your current Python, rename .build\\.venv (do not delete other project files) and rerun RUN.bat."
        }
        return $exe'''
    assert oldblock in s
    s=s.replace(oldblock,'''        if (([string]$currentFamily).Trim() -eq ([string]$venvFamily).Trim()) {
            Write-Host '[AVENA] Reusing compatible virtual environment.' -ForegroundColor Green
            return $exe
        }
        Write-Host '[AVENA] Interpreter changed; preserving previous environment.' -ForegroundColor Yellow''')
    oldblock='''    if (Test-Path $venv) {
        throw "Existing .build\\.venv cannot run or has Python older than 3.11 / non-x64: $venv . Rename/remove that virtual environment only, then re-run RUN.bat."
    }'''
    assert oldblock in s
    s=s.replace(oldblock,'''    if (Test-Path $venv) {
        $previous = Join-Path $BuildRoot ('.venv.previous-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,6))
        Move-Item -LiteralPath $venv -Destination $previous -ErrorAction Stop
        Write-Host "[AVENA] Old environment preserved: $previous" -ForegroundColor Yellow
    }''')
    assert "-c', 'import sys" not in s and " -c 'import sys" not in s
    common.write_text(s,encoding="utf-8")
    probe=new/"scripts/python_probe.py"
    probe.write_text('''"""Interpreter probe avoids PowerShell native -c quoting."""
import sys
if sys.version_info < (3, 11) or sys.maxsize <= 2**32:
    print("AVENA_RUNTIME_UNSUPPORTED")
    raise SystemExit(6)
print("AVENA_RUNTIME|%d|%d|%d|64" % sys.version_info[:3])
''',encoding="utf-8")
    gui=new/"app/gui.py"
    s=gui.read_text(encoding="utf-8")
    s=s.replace('        self._licensed = False\\n','        self._licensed = False\\n        self.license_label_text=tk.StringVar(value="لایسنس: در انتظار بررسی")\\n',1)
    s=s.replace('        self._licensed = True\\n        self._cloud_manual_stop','        self._licensed = True\\n        self.license_label_text.set("● لایسنس دستگاه فعال است")\\n        self._cloud_manual_stop',1)
    target='        self.text(right,"آونا الکتریکال",20,"text",True).pack(anchor="e")'
    assert target in s
    s=s.replace(target,target+'\\n        tk.Label(right,textvariable=self.license_label_text,bg=COL["panel"],fg=COL["accent"],font=(self.font,9,"bold")).pack(anchor="e",pady=(3,0))',1)
    gui.write_text(s,encoding="utf-8")
    gate=new/"app/activation_gate.py"
    s=gate.read_text(encoding="utf-8")
    target='        self.code.set("")\\n        self.window.grab_release()'
    assert target in s
    s=s.replace(target,'        self.code.set("")\\n        self.info.configure(text="لایسنس تأیید شد؛ ورود به پنل آونا ...",fg=COLORS["accent"])\\n        self.window.grab_release()',1)
    gate.write_text(s,encoding="utf-8")
    version=new/"app/__init__.py"
    version.write_text(version.read_text(encoding="utf-8").replace("0.9.0","0.9.1"),encoding="utf-8")
    (new/"README_HOTFIX_FA.txt").write_text("""Avena Electrical 0.9.1
RUN.bat: fix interpreter inspection on second launch; separate Python probe; preserve incompatible .venv and rebuild.
License: once activated, the dialog closes normally; a persistent green license indicator appears in the main app.
This is a Windows Python SOURCE release, not prebuilt EXE. Requires Python 3.11+ x64.
Run RUN.bat from extracted source folder. Do not run two copies simultaneously.
Before sending AutoCAD drawing commands, approve locally. No automatic DWG save/delete.
""",encoding="utf-8")
    out.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(out,"w",ZIP_DEFLATED,compresslevel=8) as archive:
        for file in new.rglob("*"):
            if file.is_file():archive.write(file,file.relative_to(root))
    with ZipFile(out) as archive:
        assert archive.testzip() is None
        print("RELEASE_OK",len(archive.namelist()),out.stat().st_size)
