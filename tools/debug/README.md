# Scooby-Doo: Refrightened — debug kit

Tools and Claude Code skills for finding bugs in the
[Scooby-Doo: Refrightened](https://github.com/josiahg2502-glitch/Scooby-Doo-Refrightened) static recomp. Only things that
helped in a real investigation (PRs #8, #10–#14) or will help the next one. Upstream tools (`tools\build-no100f.ps1`,
`shot-pid.ps1`, ...) stay in the recomp repo; nothing here contains game data.

## Install

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1 [-Recomp <path to the recomp checkout>]
```

Creates two junctions in the recomp checkout and adds them to its `.git\info\exclude`:

| In the recomp | Points to |
| --- | --- |
| `.claude\skills` | `skills\` |
| `tools\debug` | `tools\` |

All paths in the skills are written from the recomp root (`tools\debug\...`). `tools\local\` is git-ignored: keep the
user's own `Config.toml` there as `Config.user.toml` (session scripts restore it) and machine-local Dolphin disc copies.

## Skills

| Skill | Use for |
| --- | --- |
| `hle-divergence-debug` | Geometry/state/GPU bugs: guest data integrity, native override vs original, Dolphin DFF oracle. Cases: PR #8 (+ ghost regression), #10, #12/#13 |
| `game-logic-debug` | Frame-rate (fps60) and gameplay bugs: fixed spawn spots, F8 dev menu (any scene, saved spots, god mode, monsters off), live memory (postool), particle pool/emitter counts, flicker measurement. Case: PR #14 |
| `manual-yn-bisect` | Locked landing + in-game Y/N toast for human visual checks; fix-only PR workflow (`strip-before-pr.md`) |
| `audio-debug` | Crackle/clicks/fuzz: capture, per-stage dumps, disc reference decode. Case: PR #11 |

## Tools

| Path | What |
| --- | --- |
| `play-patched.ps1` | Apply patches (default `devmenu`: F8 dev menu), build, play; patches come out of the source when the game closes. `-Patch a,b`, `-Keep`, `-CleanBuild`, `-Remove` |
| `manual-session.ps1` | Single-window playtest: `start -Boot <level> [-AllPowerups]` (writes Config + `zz-manual` boot mod), `shot`, `stop`, `stop-tests` |
| `dol.py` | `callers` / `func` / `dis` / `name` on `game/main.dol` with MAP names (needs `capstone`) |
| `overrides.py` | Active native overrides; `--effects`, `--xref` (`__GXData` fields only the replaced original maintained) |
| `dff/` | Dolphin `.dff` FIFO log decoder, renders, pool/dynamic-array listers |
| `audio/` | `crackle.py` click detector, `adpcm_ref.py` disc reference decode + bit-exact compare, `hip.py` HIP asset lister |
| `game/` | `levels.md` (scene IDs ↔ level names, which scenes to test what in) + `levels.py` (reads the table from `main.dol`), `mkhip.py` (spawn spot / move NPCs via the boot mod), `spots.txt`, `findpos.py`, `addrrefs.py`, `parsys.py`, `births.py` + `births-run.ps1` |
| `capture/` | `get-ffmpeg.ps1` + `ffbin.py` (find or fetch ffmpeg), `record.ps1` (gdigrab of the game window), `flashcount.py` (one-frame flash counter), `triplet.py` |
| `yn-bisect/` | `curtain-repro.ps1` scripted landing template, `curtain-ask.ps1` Y/N toast helper (need `yn-bisect-harness.patch`) |
| `holiday-shots.ps1` | Screenshot loop for `[game] holiday` dates per hub (needs PR #13) |
| `patches/` | Diagnostics kept out of PRs; table in `skills/manual-yn-bisect/strip-before-pr.md` |

Patches are against upstream `main` `e600261` unless the table says otherwise. `gx-draw-probes.patch` was rebased onto
PR #8 `622b97a` for this repo and not rebuilt since.

Requirements: Python 3 with numpy + Pillow (+ `capstone` for `dol.py`/`overrides.py`). The `capture\` tools use ffmpeg from
PATH; without one, `capture\get-ffmpeg.ps1` downloads the BtbN win64 GPL build once into `tools\local\ffmpeg` (SHA-256 checked).
