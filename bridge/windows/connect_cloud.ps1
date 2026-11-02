$ErrorActionPreference='Stop'
function Read-Secret([string]$Prompt) {
  $s=Read-Host -AsSecureString $Prompt
  $b=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
  try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }
}
$EnvDir=Join-Path $PSScriptRoot '.bridge-venv'
try {
  $python=Get-Command py -ErrorAction Stop
  if (-not (Test-Path (Join-Path $EnvDir 'Scripts/python.exe'))) {
     & py -3 -m venv $EnvDir
     if ($LASTEXITCODE -ne 0) { throw 'Unable to create Python environment.' }
  }
  $exe=Join-Path $EnvDir 'Scripts/python.exe'
  & $exe -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
  if ($LASTEXITCODE -ne 0) { throw 'Dependencies unavailable; check network connection.' }
  Write-Host '[AVENA] Local AutoCAD MCP must already be running on port 18327.' -ForegroundColor Cyan
  $env:AVENA_AGENT_TOKEN=Read-Secret 'Cloud agent token'
  $env:AVENA_LOCAL_MCP_TOKEN=Read-Secret 'Local Avena MCP bearer token (new, rotated)'
  if ($env:AVENA_AGENT_TOKEN.Length -lt 40 -or $env:AVENA_LOCAL_MCP_TOKEN.Length -lt 32) { throw 'Token too short.' }
  & $exe (Join-Path $PSScriptRoot 'agent.py')
  if ($LASTEXITCODE -ne 0) { throw 'Agent failed.' }
} catch { Write-Host $_.Exception.Message -ForegroundColor Red; exit 1 }
finally { Remove-Item Env:AVENA_AGENT_TOKEN -ErrorAction SilentlyContinue; Remove-Item Env:AVENA_LOCAL_MCP_TOKEN -ErrorAction SilentlyContinue }
