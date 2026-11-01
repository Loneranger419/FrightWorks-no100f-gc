# Wait for in-game Y/N while a toast is showing.
# Game writes Play\curtain-answer.txt ("y" or "n") when the player presses Y or N.
#
#   . tools\debug\yn-bisect\curtain-ask.ps1
#   $ans = Wait-CurtainAnswer -Toast 'Do you still see purple curtain spikes?' -TimeoutSec 120
#
# Needs a build with tools\debug\patches\yn-bisect-harness.patch applied (toast + Y/N keys + skip/flat files).
param()

$ErrorActionPreference = 'Stop'
$script:RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path

function Set-CurtainToast([string]$msg) {
    $path = Join-Path $script:RepoRoot 'Play\curtain-test-toast.txt'
    if ([string]::IsNullOrEmpty($msg)) { Remove-Item $path -ErrorAction SilentlyContinue }
    else { [System.IO.File]::WriteAllText($path, $msg) }
}

function Set-CurtainEvents([string]$range) {
    $path = Join-Path $script:RepoRoot 'Play\curtain-skip-events.txt'
    if ([string]::IsNullOrEmpty($range)) { Remove-Item $path -ErrorAction SilentlyContinue }
    else { [System.IO.File]::WriteAllText($path, $range) }
}

function Set-CurtainSizes([string]$sizes) {
    $path = Join-Path $script:RepoRoot 'Play\curtain-skip-sizes.txt'
    if ([string]::IsNullOrEmpty($sizes)) { Remove-Item $path -ErrorAction SilentlyContinue }
    else { [System.IO.File]::WriteAllText($path, $sizes) }
}

function Set-CurtainSig([string]$sig) {
    $path = Join-Path $script:RepoRoot 'Play\curtain-skip-sig.txt'
    if ([string]::IsNullOrEmpty($sig)) { Remove-Item $path -ErrorAction SilentlyContinue }
    else { [System.IO.File]::WriteAllText($path, $sig) }
}

function Set-CurtainFlat([string]$range) {
    # Paint host events a-b flat white (geometry kept). Empty clears.
    $path = Join-Path $script:RepoRoot 'Play\curtain-flat-events.txt'
    if ([string]::IsNullOrEmpty($range)) { Remove-Item $path -ErrorAction SilentlyContinue }
    else { [System.IO.File]::WriteAllText($path, $range) }
}

function Clear-CurtainAnswer {
    Remove-Item (Join-Path $script:RepoRoot 'Play\curtain-answer.txt') -ErrorAction SilentlyContinue
}

function Wait-CurtainAnswer {
    param(
        [Parameter(Mandatory = $true)][string]$Toast,
        [int]$TimeoutSec = 180,
        [string]$Events = '',
        [string]$Sizes = '',
        [string]$Sig = '',
        [string]$Flat = '',
        [string]$ShotLabel = ''
    )
    Clear-CurtainAnswer
    # Always clear all skip controls first so a prior Events range cannot linger under a Sig-only ask.
    Set-CurtainEvents ''
    Set-CurtainSizes ''
    Set-CurtainSig ''
    Set-CurtainFlat ''
    Set-CurtainEvents $Events
    Set-CurtainSizes $Sizes
    Set-CurtainSig $Sig
    Set-CurtainFlat $Flat
    Set-CurtainToast $Toast
    Write-Host "ASK: $Toast"
    Write-Host '     waiting for in-game [Y]=yes or [N]=no ...'
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $answerPath = Join-Path $script:RepoRoot 'Play\curtain-answer.txt'
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $answerPath) {
            $raw = (Get-Content -LiteralPath $answerPath -Raw).Trim().ToLowerInvariant()
            if ($raw -eq 'y' -or $raw -eq 'n') {
                if ($ShotLabel) {
                    powershell -ExecutionPolicy Bypass -File (Join-Path $script:RepoRoot 'tools\debug\manual-session.ps1') shot -Label $ShotLabel | Out-Host
                }
                Write-Host "ANSWER: $raw"
                return $raw
            }
        }
        Start-Sleep -Milliseconds 200
    }
    throw "Wait-CurtainAnswer timed out after ${TimeoutSec}s - no Y/N from game"
}

# If invoked directly, run a smoke prompt.
if ($MyInvocation.InvocationName -ne '.' -and $MyInvocation.Line -notmatch '^\s*\.') {
    Set-Location $script:RepoRoot
    $a = Wait-CurtainAnswer -Toast 'SMOKE: press Y for yes, N for no (keyboard focus on game)' -TimeoutSec 120
    Set-CurtainToast ''
    Write-Host "smoke answer=$a"
}
