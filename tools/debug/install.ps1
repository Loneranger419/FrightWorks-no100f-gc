# Link this repo into a Scooby-Doo: Refrightened checkout:
#   <recomp>\.claude\skills -> <this repo>\skills    (Claude Code project skills)
#   <recomp>\tools\debug    -> <this repo>\tools     (debug tools; scripts find the recomp root as tools\debug\..\..)
# and make sure the recomp's .git\info\exclude hides both, so they never ride along in a PR.
#
#   powershell -ExecutionPolicy Bypass -File install.ps1 [-Recomp <path>]   (default: ..\Scooby-Doo-ReFrightened)
# Junctions need no admin rights. An existing real folder at a link path is never touched: move it away first.
param([string]$Recomp = (Join-Path (Split-Path -Parent $PSScriptRoot) 'Scooby-Doo-ReFrightened'))
$ErrorActionPreference = 'Stop'
$Recomp = (Resolve-Path $Recomp).Path
if (-not (Test-Path (Join-Path $Recomp 'wiicompiled'))) { throw "$Recomp does not look like the recomp checkout (no wiicompiled\)" }

$links = @(
    @{ Path = Join-Path $Recomp '.claude\skills'; Target = Join-Path $PSScriptRoot 'skills' },
    @{ Path = Join-Path $Recomp 'tools\debug'; Target = Join-Path $PSScriptRoot 'tools' }
)
foreach ($l in $links) {
    $item = Get-Item -LiteralPath $l.Path -Force -ErrorAction SilentlyContinue
    if ($item -and $item.LinkType -eq 'Junction') {
        if (($item.Target | Select-Object -First 1) -eq $l.Target) { "ok      $($l.Path)"; continue }
        Remove-Item -LiteralPath $l.Path -Force   # removes only the junction, not its target
    } elseif ($item) {
        throw "$($l.Path) is a real folder; move it away, then re-run"
    }
    New-Item -ItemType Directory -Force (Split-Path -Parent $l.Path) | Out-Null
    New-Item -ItemType Junction -Path $l.Path -Target $l.Target | Out-Null
    "linked  $($l.Path) -> $($l.Target)"
}

$exclude = Join-Path $Recomp '.git\info\exclude'
$lines = @(Get-Content -LiteralPath $exclude -ErrorAction SilentlyContinue)
foreach ($p in '.claude/', 'tools/debug/') {
    if ($lines -notcontains $p) { Add-Content -LiteralPath $exclude -Value $p; "exclude += $p" }
}
if (-not (Test-Path (Join-Path $PSScriptRoot 'tools\local\Config.user.toml'))) {
    "note: no tools\local\Config.user.toml yet - copy your Play\UserData\Config.toml there before test sessions (scripts restore it)"
}
