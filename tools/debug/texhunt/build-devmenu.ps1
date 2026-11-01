# build-devmenu.ps1 -Branch <branch>: build Play\ from that branch with the dev menu patch, then put the source back
# (patch removed, the branch that was checked out before). Needs a clean tree apart from untracked files.
# Used by spots-run.ps1 -Branch; hunt.ps1 -Branch switches branches itself (play-patched builds and applies the patch).
#   e.g. main (no PR #22), pr/hd-alpha-cutoff (main + #22), release/1.0.3-beta (no #22), fix/hd-alpha-cutoff (beta + #22)
param([Parameter(Mandatory)][string]$Branch)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path   # repo root
Set-Location $root
$patch = Join-Path $root 'tools\debug\patches\devmenu.patch'

if (git status --porcelain --untracked-files=no) { throw 'uncommitted changes: commit or stash them first' }
$before = git branch --show-current
git checkout -q $Branch
if ($LASTEXITCODE -ne 0) { throw "git checkout $Branch failed" }
try {
    git apply $patch
    if ($LASTEXITCODE -ne 0) { throw "devmenu.patch does not apply on $Branch" }
    try {
        Remove-Item Env:NO100F_*, Env:AX_* -ErrorAction SilentlyContinue
        & powershell -ExecutionPolicy Bypass -File (Join-Path $root 'tools\build-no100f.ps1') -SkipTools *>&1 |
            Select-String -Pattern 'error|DONE|copied' | ForEach-Object { "build     $_" }
        if ($LASTEXITCODE -ne 0) { throw 'build failed' }
    } finally {
        git apply -R $patch
    }
} finally {
    git checkout -q $before
    "build     Play\ = $Branch + dev menu; source back on $before"
}
