# Single-window manual playtest helper for texture / visual bugs.
# Never spawns workers, never scripts input, never auto-kills after N seconds.
#
#   powershell -ExecutionPolicy Bypass -File tools\debug\manual-session.ps1 start
#   powershell -ExecutionPolicy Bypass -File tools\debug\manual-session.ps1 shot [-Label glitch]
#   powershell -ExecutionPolicy Bypass -File tools\debug\manual-session.ps1 status
#   powershell -ExecutionPolicy Bypass -File tools\debug\manual-session.ps1 stop
#   powershell -ExecutionPolicy Bypass -File tools\debug\manual-session.ps1 stop-tests   # kill leftover automations only
#
# Default boot (when -Boot is omitted): e001 — first Hedge Maze section
# ("On Edge in the Hedge 1"). Override with -Boot <level> if needed.
#   ... start -Boot h002
# Unlock every eSPECIAL_* gadget in sd2.ini (springs, helmet, etc.):
#   ... start -AllPowerups
#   ... start -Boot g001 -AllPowerups
#
# Shots land in autotest\manual\. Session state in autotest\manual\session.json.
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'shot', 'status', 'stop', 'stop-tests')]
    [string]$Command = 'status',

    [string]$Boot = 'e001',
    [string]$Label = '',
    [switch]$HdTextures,
    [switch]$AllPowerups,
    [int]$Width = 1600,
    [int]$Height = 900
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0

$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path  # this file is tools\debug\manual-session.ps1
$play = Join-Path $root 'Play'
$exe = Join-Path $play 'FrightWorks Game.exe'
$outDir = Join-Path $root 'autotest\manual'
$statePath = Join-Path $outDir 'session.json'
$disc = Join-Path $root 'Disc\DATA'

function Stop-AutomationLeftovers {
    $patterns = @(
        '_verify_playground', '_verify_fix', '_repro_multi', '_probe_i001',
        'level-sweep', 'verify-playground', 'verify-fix', 'NSMBW_INPUT_SCRIPT'
    )
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | ForEach-Object {
        $cmd = $_.CommandLine
        $path = $_.ExecutablePath
        if (-not $cmd -and -not $path) { return }
        $hit = $false
        foreach ($p in $patterns) {
            if (($cmd -and $cmd -match [regex]::Escape($p)) -or ($path -and $path -match [regex]::Escape($p))) {
                $hit = $true; break
            }
        }
        # Any game copy running from autotest\ work trees (never from Play\).
        if ($path -and $path -match '[\\/]autotest[\\/]') { $hit = $true }
        if ($hit) {
            Write-Host "automation: kill $($_.ProcessId) $($_.Name)"
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
}

function Get-PlayGameProcesses {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match 'Scooby' -and $_.ExecutablePath -and (
            $_.ExecutablePath -eq $exe -or
            ((Split-Path $_.ExecutablePath -Parent) -eq $play)
        )
    }
}

function Read-Session {
    if (-not (Test-Path -LiteralPath $statePath)) { return $null }
    return (Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json)
}

function Write-Session([hashtable]$data) {
    [IO.Directory]::CreateDirectory($outDir) | Out-Null
    ($data | ConvertTo-Json) | Set-Content -LiteralPath $statePath -Encoding utf8
}

function Assert-PlayReady {
    if (-not (Test-Path -LiteralPath $exe)) {
        throw "Missing $exe - build with tools\build-no100f.ps1 first."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $disc 'sys\main.dol'))) {
        throw "Missing Disc\DATA - extract the ISO first."
    }
}

function Write-PlayConfig([string]$bootLevel, [bool]$unlockAllPowerups) {
    [IO.Directory]::CreateDirectory((Join-Path $play 'UserData')) | Out-Null
    # Never leave a sweep mod that overrides BOOT behind.
    Remove-Item -Recurse -Force (Join-Path $play 'UserData\mods\zz-sweep') -ErrorAction SilentlyContinue

    $dvd = ($disc -replace '\\', '/')
    $hd = if ($HdTextures) { 'true' } else { 'false' }
    @"
[paths]
dvd_root = '$dvd'

[video]
display_mode = "windowed"
window_width = $Width
window_height = $Height
resolution_multiplier = 0
aspect_mode = 1
skip_intro = true
fps60 = true
msaa = 4
texture_replacements = $hd
"@ | Set-Content -LiteralPath (Join-Path $play 'UserData\Config.toml') -Encoding utf8

    $needIni = [bool]$bootLevel -or $unlockAllPowerups
    if (-not $needIni) {
        Remove-Item -Recurse -Force (Join-Path $play 'UserData\mods\zz-manual') -ErrorAction SilentlyContinue
        Write-Host 'boot: game default / menu (no BOOT override, stock powerups)'
        return
    }

    $modFiles = Join-Path $play 'UserData\mods\zz-manual\files'
    [IO.Directory]::CreateDirectory($modFiles) | Out-Null
    $iniPath = Join-Path $disc 'files\sd2.ini'
    $latin1 = [Text.Encoding]::GetEncoding(28591)
    $ini = [IO.File]::ReadAllText($iniPath, $latin1)
    if ($bootLevel) {
        $ini = [regex]::Replace($ini, '(?m)^BOOT=.*$', "BOOT=$bootLevel")
        $ini = [regex]::Replace($ini, '(?m)^ShowMenuOnBoot=1', 'ShowMenuOnBoot=0')
        Write-Host "boot override: BOOT=$bootLevel (single window, no input script)"
    } else {
        Write-Host 'boot: game default / menu (no BOOT override)'
    }
    if ($unlockAllPowerups) {
        # Disc sd2.ini ships every eSPECIAL_* at 0; set all of them to 1 via mod overlay.
        $ini = [regex]::Replace($ini, '(?m)^(eSPECIAL_\S+\s*=\s*)\d+', '${1}1')
        $count = ([regex]::Matches($ini, '(?m)^eSPECIAL_\S+\s*=\s*1')).Count
        Write-Host "powerups: unlocked $count eSPECIAL_* flags (springs, helmet, etc.)"
    }
    [IO.File]::WriteAllText((Join-Path $modFiles 'sd2.ini'), $ini, $latin1)
}

switch ($Command) {
    'stop-tests' {
        Stop-AutomationLeftovers
        Write-Host 'stop-tests: done'
    }
    'stop' {
        Stop-AutomationLeftovers
        foreach ($p in Get-PlayGameProcesses) {
            Write-Host "stop: kill Play instance $($p.ProcessId)"
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        }
        Remove-Item -LiteralPath $statePath -ErrorAction SilentlyContinue
        Write-Host 'stop: session cleared'
    }
    'status' {
        $session = Read-Session
        $procs = @(Get-PlayGameProcesses)
        if ($procs.Count -eq 0) {
            Write-Host 'status: no Play game running'
            if ($session) { Write-Host "status: stale session.json pid=$($session.pid)" }
            exit 1
        }
        foreach ($p in $procs) {
            Write-Host "status: alive pid=$($p.ProcessId) path=$($p.ExecutablePath)"
        }
        if ($session) {
            Write-Host "status: session boot=$($session.boot) allPowerups=$($session.allPowerups) started=$($session.started)"
        }
        if ($procs.Count -gt 1) {
            Write-Host 'status: WARNING more than one Play instance - use stop then start'
            exit 2
        }
    }
    'start' {
        Assert-PlayReady
        Stop-AutomationLeftovers
        $existing = @(Get-PlayGameProcesses)
        if ($existing.Count -gt 0) {
            Write-Host "start: already running pid=$($existing[0].ProcessId) - not launching another"
            Write-Host 'start: use "shot" to capture, or "stop" then "start" to relaunch'
            exit 0
        }
        # Refuse to start if other Scooby copies are still up outside Play (shouldn't after stop-tests).
        $strays = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            $_.Name -match 'Scooby' -and $_.ExecutablePath -and $_.ExecutablePath -ne $exe
        }
        if ($strays) {
            foreach ($s in $strays) {
                Write-Host "start: killing stray $($s.ProcessId) $($s.ExecutablePath)"
                Stop-Process -Id $s.ProcessId -Force -ErrorAction SilentlyContinue
            }
            Start-Sleep -Seconds 1
        }
        Write-PlayConfig -bootLevel $Boot -unlockAllPowerups:([bool]$AllPowerups)
        # Inherit caller env into the game process (Start-Process default). Log selected diags if set.
        foreach ($name in @(
                'SPM_TEX_NOCACHE', 'NSMBW_NO_TEXMEMO', 'SPM_FLAT_TEST', 'NSMBW_NO_MERGE',
                'NSMBW_INPUT_SCRIPT', 'NSMBW_SCRIPT_REMOTES',
                'NO100F_IDX_CHECK', 'NO100F_CURTAIN_TRACE', 'NO100F_TAIL_SKIP', 'NO100F_VTX_IDX', 'NO100F_SKIP_LINES',
                'NO100F_SKIP_DEEP_IDX', 'NO100F_SKIP_CURTAIN_PANEL', 'NO100F_SKIP_CURTAIN_HEM',
                'NO100F_DROP_DEGEN_IDX', 'NO100F_GPU_OWNER', 'NO100F_GPU_OWNER_FILE',
                'NO100F_GPU_OWNER_FRAME', 'NO100F_GPU_OWNER_MAX', 'NO100F_SKIP_GPU_EVENTS',
                'NO100F_XF_REJECT_LOG', 'NO100F_NTG0_REPAIR', 'NO100F_SKIP_POS_SIZES'
            )) {
            $v = [Environment]::GetEnvironmentVariable($name, 'Process')
            if ($null -ne $v -and $v -ne '') {
                Write-Host "diag: $name=$v (inherited by game)"
            }
        }
        $p = Start-Process -FilePath $exe -WorkingDirectory $play -PassThru
        Write-Session @{
            pid         = $p.Id
            boot        = $Boot
            allPowerups = [bool]$AllPowerups
            started     = (Get-Date).ToString('o')
            exe         = $exe
        }
        Write-Host "start: launched pid=$($p.Id)"
        Write-Host "start: exe=$exe"
        Write-Host 'start: walk wherever you want; run "shot" to capture, "stop" when done'
        Write-Host 'start: Curtains F8 or Xbox LB: once at window (trace ON + shot); flutter hems; again to stop (trace OFF + shot)'
    }
    'shot' {
        # Do not kill anything here - only capture the Play window.
        $procs = @(Get-PlayGameProcesses)
        if ($procs.Count -eq 0) { throw 'shot: no Play game running - use start first' }
        if ($procs.Count -gt 1) { throw 'shot: multiple Play instances - run stop, then start' }
        $gamePid = [int]$procs[0].ProcessId
        [IO.Directory]::CreateDirectory($outDir) | Out-Null
        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        $suffix = if ($Label) { "-$Label" } else { '' }
        $out = Join-Path $outDir "shot-$stamp$suffix.png"
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'tools\shot-pid.ps1') `
            -ProcessId $gamePid -Out $out
        if (-not (Test-Path -LiteralPath $out)) { throw "shot: capture failed for pid=$gamePid" }
        $bytes = (Get-Item -LiteralPath $out).Length
        Write-Host "shot: $out ($bytes bytes)"
    }
}
