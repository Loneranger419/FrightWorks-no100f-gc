# Print the folder holding ffmpeg.exe + ffprobe.exe: from PATH, else tools\debug\local\ffmpeg\bin, else download a local copy there
# (BtbN win64 GPL build from GitHub, SHA-256 checked against the release's checksums.sha256; GPL for libx264).
#   $bin = & tools\debug\capture\get-ffmpeg.ps1 [-SkipPath]     -SkipPath ignores PATH (tests the local copy / download)
# Only the folder goes to stdout; progress goes to stderr, so callers can capture the output.
param([switch]$SkipPath)
$ErrorActionPreference = 'Stop'
$local = Join-Path $PSScriptRoot '..\local\ffmpeg'
$localBin = Join-Path $local 'bin'
function Log($m) { [Console]::Error.WriteLine("get-ffmpeg: $m") }

if (-not $SkipPath) {
    $ff = Get-Command ffmpeg -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    $fp = Get-Command ffprobe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($ff -and $fp) { return Split-Path -Parent $ff.Source }
}
if ((Test-Path (Join-Path $localBin 'ffmpeg.exe')) -and (Test-Path (Join-Path $localBin 'ffprobe.exe'))) { return (Resolve-Path $localBin).Path }

$name = 'ffmpeg-master-latest-win64-gpl.zip'
$base = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest'
$tmp = Join-Path ([IO.Path]::GetTempPath()) "get-ffmpeg-$PID"
New-Item -ItemType Directory -Force $tmp | Out-Null
try {
    $ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest is very slow with the progress bar
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Log "ffmpeg not found; downloading $name"
    Invoke-WebRequest "$base/$name" -OutFile (Join-Path $tmp $name) -UseBasicParsing
    Invoke-WebRequest "$base/checksums.sha256" -OutFile (Join-Path $tmp 'checksums.sha256') -UseBasicParsing
    $want = (Get-Content (Join-Path $tmp 'checksums.sha256') | Where-Object { $_ -match "\s\*?$([regex]::Escape($name))$" } | Select-Object -First 1) -split '\s+' | Select-Object -First 1
    $got = (Get-FileHash (Join-Path $tmp $name) -Algorithm SHA256).Hash
    if (-not $want -or $got -ne $want.ToUpper()) { throw "SHA-256 mismatch for $name (expected $want, got $got)" }
    Log "checksum ok, extracting"
    Expand-Archive (Join-Path $tmp $name) -DestinationPath (Join-Path $tmp 'x') -Force
    $top = Get-ChildItem (Join-Path $tmp 'x') -Directory | Select-Object -First 1   # the zip holds one ffmpeg-<version>\ folder
    if (Test-Path $local) { Remove-Item -Recurse -Force $local }
    New-Item -ItemType Directory -Force (Split-Path -Parent $local) | Out-Null
    Move-Item $top.FullName $local
} finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}
Log "installed to $((Resolve-Path $localBin).Path)"
(Resolve-Path $localBin).Path
