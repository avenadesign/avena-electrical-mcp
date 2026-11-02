$ErrorActionPreference='Stop'
$Host.UI.RawUI.WindowTitle='Avena Electrical - Secure Cloud Connection'
function Read-AvenaSecret([string]$Prompt) {
    $s=Read-Host -Prompt $Prompt -AsSecureString
    $p=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($p) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($p) }
}
try {
    $Python='py'
    $PyArgs=@('-3')
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python 3 is missing. Install Python 3.11+ x64.' }
        $Python='python'
        $PyArgs=@()
    }
    & $Python @PyArgs -c 'import sys; assert sys.version_info >= (3, 11) and sys.maxsize > 2**32, "Python 3.11+ x64 required"'
    if ($LASTEXITCODE -ne 0) { throw 'Installed Python must be 3.11 or newer, 64-bit.' }
    $agent=Join-Path $PSScriptRoot 'stdlib_agent.py'
    if (-not (Test-Path $agent)) { throw 'stdlib_agent.py is missing from this directory.' }
    $socket=New-Object System.Net.Sockets.TcpClient
    try {
        $task=$socket.ConnectAsync('127.0.0.1',18327)
        if (-not $task.Wait(2500)) { throw 'Local AutoCAD MCP is not listening on 18327. Start Avena GUI > Run MCP first.' }
    } finally { $socket.Dispose() }
    Write-Host '[AVENA] Local port 18327 detected. Tokens are not stored to disk.' -ForegroundColor Green
    $env:AVENA_AGENT_TOKEN=Read-AvenaSecret 'Avena SERVER AGENT token (from /etc/avena-elc/bridge.env)'
    $env:AVENA_LOCAL_MCP_TOKEN=Read-AvenaSecret 'Local MCP token (copied from Avena GUI)'
    if ($env:AVENA_AGENT_TOKEN.Length -lt 40 -or $env:AVENA_LOCAL_MCP_TOKEN.Length -lt 32) { throw 'Invalid token length.' }
    Write-Host '[AVENA] Connecting to https://elc.avenaai.ir ...' -ForegroundColor Cyan
    & $Python @PyArgs $agent
    if ($LASTEXITCODE -ne 0) { throw 'Cloud connection failed.' }
} catch {
    Write-Host "[AVENA] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    Remove-Item Env:AVENA_AGENT_TOKEN -ErrorAction SilentlyContinue
    Remove-Item Env:AVENA_LOCAL_MCP_TOKEN -ErrorAction SilentlyContinue
}
