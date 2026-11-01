# fogdump.ps1 -Label <name>: i004 fog bank state from the running dev menu build (Play\devmenu.txt peeks).
# Finds PAREMIT_FOGBANK (480499F3) in the scene list, its system (+0x14), peeks the particle pool and summarises the
# fog particles (fogsum.py). Logs kept as autotest\fanfog\<label>-*.log.
param([Parameter(Mandatory)][string]$Label)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path   # repo root
$play = Join-Path $root 'Play'
$out = Join-Path $root 'autotest\fanfog'
New-Item -ItemType Directory -Force $out | Out-Null
$cmd = Join-Path $play 'devmenu.txt'
$log = Join-Path $play 'devmenu.log'

function Run([string[]]$lines, [string]$name) {
    Remove-Item $log -ErrorAction SilentlyContinue
    Set-Content $cmd $lines
    $t = Get-Date
    while (((Get-Date) - $t).TotalSeconds -lt 30) {
        if ((Test-Path $log) -and -not (Test-Path $cmd)) { Start-Sleep -Milliseconds 500; break }
        Start-Sleep -Milliseconds 300
    }
    if (-not (Test-Path $log)) { throw "dev menu did not answer (game in play?)" }
    $dst = Join-Path $out "$Label-$name.log"
    Copy-Item $log $dst -Force
    $dst
}

$ents = Get-Content (Run @('ents') 'ents')
$row = $ents | Where-Object { $_ -match ' id 480499F3 ' } | Select-Object -First 1
if (-not $row) { throw 'PAREMIT_FOGBANK not in the scene list (not in i004?)' }
$emitter = ($row -split '\s+')[2]
$em = Get-Content -Raw (Run @("peek $emitter 8") 'emitter')
if ($em -notmatch '\+14 ([0-9A-F]{8})') { throw 'emitter peek failed' }
$system = $Matches[1]
$pool = Run @("peek $emitter 8", "peek $system 4", 'peek 80210858 40000', 'where') 'pool'
& python (Join-Path $PSScriptRoot 'fogsum.py') $pool $emitter
