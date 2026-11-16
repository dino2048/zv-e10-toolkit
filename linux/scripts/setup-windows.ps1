# Prepare the toolkit host environment. Does not connect to a camera.
# pip ignores HTTP_PROXY/HTTPS_PROXY by design, so pass -Proxy when needed.
param(
    [string]$Python = 'py',
    [string]$Proxy = ''
)
$ErrorActionPreference = 'Stop'
$linuxDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$venv = Join-Path $linuxDir '.venv'
$venvPython = Join-Path $venv 'Scripts/python.exe'
$pmca = Join-Path $linuxDir 'vendor/Sony-PMCA-RE'
$pmcaRevision = 'a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0'

if (-not (Test-Path -LiteralPath $venvPython)) {
    & $Python -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed' }
}
$pipArgs = @('-m', 'pip', 'install')
if ($Proxy) { $pipArgs += @('--proxy', $Proxy) }
$pipArgs += @('-r', (Join-Path $linuxDir 'requirements.txt'))
& $venvPython @pipArgs
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed' }

if (-not (Test-Path -LiteralPath $pmca)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $pmca) | Out-Null
    $gitArgs = @()
    if ($Proxy) { $gitArgs += @('-c', "http.proxy=$Proxy") }
    $gitArgs += @('clone', '--no-checkout', 'https://github.com/ma1co/Sony-PMCA-RE.git', $pmca)
    & git @gitArgs
    if ($LASTEXITCODE -ne 0) { throw 'Sony-PMCA-RE clone failed' }
    & git -C $pmca checkout --detach $pmcaRevision
    if ($LASTEXITCODE -ne 0) { throw 'Sony-PMCA-RE checkout failed' }
}
$actual = (& git -C $pmca rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $actual -ne $pmcaRevision) {
    throw "Sony-PMCA-RE must be at $pmcaRevision; preserve the existing checkout and review it"
}

$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = $pmca
    & $venvPython -B -c 'from pmca.commands.usb import senserShellCommand'
    if ($LASTEXITCODE -ne 0) { throw 'Sony-PMCA-RE import check failed' }
} finally {
    $env:PYTHONPATH = $previousPythonPath
}
& $venvPython -B (Join-Path $linuxDir 'host/zve10_terminal_server.py') --self-test
if ($LASTEXITCODE -ne 0) { throw 'Toolkit server self-test failed' }
Write-Host "TOOLKIT_PYTHON=$venvPython"
Write-Host 'Check the USB driver separately before connecting a camera.'
