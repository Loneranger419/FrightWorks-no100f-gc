# Play a build with debug patches in it, and take them out of the source again when the game closes.
#
#   powershell -ExecutionPolicy Bypass -File tools\debug\play-patched.ps1                   # dev menu (F8)
#   ... play-patched.ps1 -Patch devmenu,postool                                            # several patches
#   ... play-patched.ps1 -SkipTranslate        # faster: only if the last build was from this branch (see AGENTS.md)
#   ... play-patched.ps1 -Keep                 # leave the patches applied (to work on them; re-export afterwards)
#   ... play-patched.ps1 -CleanBuild           # after the game closes, rebuild Play\ without the patches
#
# Steps: git apply each tools\debug\patches\<name>.patch, build, start Play\Scooby-Doo Refrightened.exe, wait for it to
# exit, then git apply -R the patches this run applied. A patch that was already applied is left as found. A patch whose
# files were edited while the game ran no longer reverses cleanly: it is left applied and the script says so.
# Removal also runs on a build failure or Ctrl+C. If the window is closed instead, run with -Remove.
#   ... play-patched.ps1 -Remove [-Patch ...]  # just take the patches out
param(
    [string[]]$Patch = @('devmenu'),
    [switch]$SkipTranslate,
    [switch]$Keep,
    [switch]$CleanBuild,
    [switch]$Remove
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path  # this file is tools\debug\play-patched.ps1 (junction)
$patchDir = Join-Path $PSScriptRoot 'patches'
$exe = Join-Path $root 'Play\Scooby-Doo Refrightened.exe'
# powershell -File passes "-Patch a,b" as one string
$names = @($Patch | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })

function Git-Apply([string[]]$GitArgs) {
    & git -C $root apply @GitArgs 2>$null
    return $LASTEXITCODE -eq 0
}

function Build([switch]$Translate) {
    $buildArgs = @('-ExecutionPolicy', 'Bypass', '-File', (Join-Path $root 'tools\build-no100f.ps1'), '-SkipTools')
    if (-not $Translate) { $buildArgs += '-SkipTranslate' }
    & powershell @buildArgs | Select-Object -Last 3
    if ($LASTEXITCODE -ne 0) { throw "build failed (exit $LASTEXITCODE)" }
}

$files = foreach ($n in $names) {
    $f = Join-Path $patchDir "$n.patch"
    if (-not (Test-Path $f)) { throw "no patch $f" }
    [pscustomobject]@{ Name = $n; File = $f }
}

if ($Remove) {
    foreach ($p in $files) {
        if (Git-Apply @('-R', '--check', $p.File)) { Git-Apply @('-R', $p.File) | Out-Null; "removed   $($p.Name)" }
        elseif (Git-Apply @('--check', $p.File)) { "not applied $($p.Name)" }
        else { "CHANGED   $($p.Name): its files differ from the patch; fix by hand (git diff)" }
    }
    return
}

if (Get-Process | Where-Object { $_.Path -eq $exe }) { throw "the game is already running from Play\; close it first" }
$applied = New-Object System.Collections.Generic.List[object]
try {
    foreach ($p in $files) {
        if (Git-Apply @('--check', $p.File)) {
            Git-Apply @($p.File) | Out-Null
            $applied.Add($p)
            "applied   $($p.Name)"
        } elseif (Git-Apply @('-R', '--check', $p.File)) {
            "already   $($p.Name) (applied before this run: left as found)"
        } else {
            throw "$($p.Name) does not apply to this branch (git apply --check $($p.File)); rebase it with git apply -3"
        }
    }

    Build -Translate:(-not $SkipTranslate)
    "playing   $(Split-Path -Leaf $exe) (patches come out when it closes)"
    $game = Start-Process -FilePath $exe -WorkingDirectory (Split-Path $exe) -PassThru
    $game.WaitForExit()
    "closed    exit code $($game.ExitCode)"
} finally {
    if ($Keep) {
        if ($applied.Count) { "kept      $($applied.Name -join ', ') (-Keep). Remove later with -Remove" }
    } else {
        for ($i = $applied.Count - 1; $i -ge 0; --$i) {
            $p = $applied[$i]
            if (Git-Apply @('-R', '--check', $p.File)) {
                Git-Apply @('-R', $p.File) | Out-Null
                "removed   $($p.Name)"
            } else {
                "LEFT IN   $($p.Name): its files were edited since it was applied. Re-export it, then run -Remove:"
                "          git diff --output=tools/debug/patches/$($p.Name).patch HEAD -- <its files>  (git add -N new files first)"
            }
        }
    }
}

if ($CleanBuild -and -not $Keep -and $applied.Count) {
    "rebuilding Play\ without the patches"
    Build
}
