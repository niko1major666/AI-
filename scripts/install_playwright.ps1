$ErrorActionPreference = "Continue"

# Resolve uv from PATH (override with $env:UV_EXE); never hardcode a machine path.
$UV = $env:UV_EXE
if (-not $UV) {
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmd) { $UV = $cmd.Source }
}
if (-not $UV -or -not (Test-Path $UV)) {
    throw "uv not found. Install uv (https://docs.astral.sh/uv/) or set UV_EXE to its full path."
}

$Root = Split-Path -Parent $PSScriptRoot
$Py   = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { throw "venv python not found at $Py. Run scripts/setup_env.ps1 first." }

& $UV pip install --python $Py playwright `
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple `
    --extra-index-url https://pypi.org/simple
& $Py -m playwright install chromium
Write-Output "playwright install done"
