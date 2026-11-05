# Build pipeline: AlbionAware.exe -> bundle OpenRadar -> Inno Setup installer
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
if (-not $root) { $root = (Get-Location).Path }
Set-Location $root

python tools\sync_avalon_maps.py
if ($LASTEXITCODE -ne 0) { throw 'Avalon map sync failed' }
if (-not (Test-Path 'data\avalon\index.json')) { throw 'Avalon map index missing' }

python -m PyInstaller --noconfirm --clean packaging\albion_aware.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }

# OpenRadar is a console app and must live next to AlbionAware.exe under OpenRadar\.
$radarSource = $root + '\OpenRadar'
$radarTarget = $root + '\dist\AlbionAware\OpenRadar'
if (-not (Test-Path ($radarSource + '\OpenRadar.exe'))) {
    throw ('Missing radar: ' + $radarSource + '\OpenRadar.exe')
}
New-Item -ItemType Directory -Force -Path $radarTarget | Out-Null
Copy-Item -Path ($radarSource + '\*') -Destination $radarTarget -Recurse -Force
if (-not (Test-Path ($radarTarget + '\OpenRadar.exe'))) {
    throw 'Failed to copy OpenRadar into dist'
}

$iscc = @(
    'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
    'C:\Program Files\Inno Setup 6\ISCC.exe'
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw 'ISCC.exe not found' }

& $iscc 'packaging\albion_aware.iss'
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup build failed' }
