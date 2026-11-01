# Debug kit

Tools and Claude Code skills for finding bugs in the FrightWorks static recomp. Only things that helped in a real
investigation (upstream PRs #8, #10–#15, #22, issue #24) or will help the next one. The build tools (`tools\build-no100f.ps1`,
`shot-pid.ps1`, ...) live one folder up; nothing here contains game data.

Until 2026-10-31 this kit was a separate repo (Scooby-Doo-Refrightened-debug) linked in with junctions. Its history was
merged in with the paths rewritten, so `git log -- tools/debug .claude/skills` shows it.

Layout (paths in the skills and scripts are written from the repo root):

| Path | What |
| --- | --- |
| `.claude\skills\` | the Claude Code skills (tracked; the rest of `.claude\` is git-ignored) |
| `tools\debug\` | these tools |
| `tools\debug\local\` | git-ignored, machine-local: the user's own game config as `Config.user.toml` (session scripts restore it), Dolphin disc copies, a downloaded ffmpeg |
| `autotest\` | git-ignored work data and output: shots (`autotest\manual\`), texture-hunt data (`autotest\texhunt\`), audio dumps, logs |

## Skills

| Skill | Use for |
| --- | --- |
| `hle-divergence-debug` | Geometry/state/GPU bugs: guest data integrity, native override vs original, Dolphin DFF oracle. Cases: PR #8 (+ ghost regression), #10, #12/#13 |
| `game-logic-debug` | Frame-rate (fps60) and gameplay bugs: fixed spawn spots, F8 dev menu (any scene, saved spots, god mode, monsters off, free camera, Textures tab), live memory (postool), particle pool/emitter counts, flicker measurement. Case: PR #14 |
| `manual-yn-bisect` | Locked landing + in-game Y/N toast for human visual checks; fix-only PR workflow (`strip-before-pr.md`) |
| `audio-debug` | Crackle/clicks/fuzz/stuck loops: capture, per-stage dumps, disc reference decode. Case: PR #11 |

## Tools

| Path | What |
| --- | --- |
| `play-patched.ps1` | Apply patches (default `devmenu`: F8 dev menu), build, play; patches come out of the source when the game closes. `-Patch a,b`, `-HdTextures` (with the HD pack), `-Keep`, `-CleanBuild`, `-Remove` |
| `manual-session.ps1` | Single-window playtest: `start -Boot <level> [-AllPowerups]` (writes Config + `zz-manual` boot mod), `shot`, `stop`, `stop-tests` |
| `build-translator.ps1` | Rebuild the translator after switching to/from a branch that changes `wiicompiled\translator` (then build without `-SkipTranslate`) |
| `dol.py` | `callers` / `func` / `dis` / `name` on `game/main.dol` with MAP names (needs `capstone`) |
| `overrides.py` | Active native overrides; `--effects`, `--xref` (`__GXData` fields only the replaced original maintained) |
| `dff/` | Dolphin `.dff` FIFO log decoder, renders, pool/dynamic-array listers |
| `audio/` | `crackle.py` click detector, `adpcm_ref.py` disc reference decode + bit-exact compare, `hip.py` HIP asset lister, `loopcheck.py` (is the output stuck repeating a short loop? `--scan W` over a long dump), `loop-capture.ps1` (boot a scene with the audio dump on, then `loopcheck.py`) |
| `game/` | `levels.md` (scene IDs ↔ level names, which scenes to test what in) + `levels.py` (reads the table from `main.dol`), `mkhip.py` (spawn spot / move NPCs via the boot mod), `spots.txt`, `findpos.py`, `addrrefs.py`, `parsys.py`, `births.py` + `births-run.ps1`, `fogdump.ps1` + `fogsum.py` (i004 fog bank state from a running dev menu build), `fanfog-walk.py` (walk one particle list from a pool peek) |
| `texhunt/` | HD texture work, see below |
| `capture/` | `get-ffmpeg.ps1` + `ffbin.py` (find or fetch ffmpeg), `record.ps1` (video of the game window: ddagrab + topmost by default, `-Method gdigrab`), `flashcount.py` (one-frame flash counter), `triplet.py` |
| `yn-bisect/` | `curtain-repro.ps1` scripted landing template, `curtain-ask.ps1` Y/N toast helper (need `yn-bisect-harness.patch`) |
| `holiday-shots.ps1` | Screenshot loop for `[game] holiday` dates per hub (needs PR #13) |
| `patches/` | Diagnostics kept out of PRs; table in `.claude\skills\manual-yn-bisect\strip-before-pr.md` |

### `texhunt/` (HD texture packs, cut-outs, halos)

Data and output go to `autotest\texhunt\` (`suspects.csv`, `devmenu_textures.txt`, `disc.pkl`, packs, shots); the
session scripts need the dev menu build in `Play\` (`build-devmenu.ps1` or `play-patched.ps1`) and restore the user's
setup when the game closes.

| Tool | What |
| --- | --- |
| `look.ps1 -Boot e005 -Spot <spot> [-Hd \| -Pack <dir>] [-Extra <dir>] [-Interp N] [-KeepIntro]` | Open the game at a saved dev-menu spot (intro cutscene skipped) and leave it to the human |
| `hunt.ps1 [-Boot h001] [-Pack <dir>] [-Branch b] [-TexLog]` | Texture-hunt session: dev menu + HD pack, every powerup, no hub intro, audio dump checked for a stuck loop |
| `spots-run.ps1 -Boot h001 -Ids a,b -Mode orig\|hd\|clean [-Tag x] [-Branch b]` | Screenshot each saved spot |
| `cutout-shots.ps1`, `perf-cutout.ps1` | Shots / draw-call + frame-time numbers per cut-out mode (needs aurora's cut-out modes) |
| `build-devmenu.ps1 -Branch b` | `Play\` = that branch + the dev menu patch, source put back afterwards |
| `gxtex.py` | XXH64 + RWTX reader + GX decoders; names textures like the port (`tex1_WxH_<hash>_<fmt>`) |
| `where.py [IDs]` | Which assets use a suspect's texture; BSP geometry gets `tp X Y Z` positions |
| `tint-pack.py --out <dir> (--from <dir> \| --hip <HIP>) [--match s]` | Tinted copies of textures; link them with `look.ps1 -Extra` to see where a texture is drawn |
| `creeper-frames.py` | The HD Creeper window frames (issue #24) from the disc originals + ScoobyHD's window (needs SciPy) |
| `skipintro.py <mod dir>` | h001.HIP without the intro cutscene (written into a boot mod, never committed) |
| `ogexport.py`, `clean.py`, `onoff.py`, `verdicts.py` | Original-vs-HD sheets (local only), cleaned and on/off test packs, dev menu marks ↔ `suspects.csv` |

Patches are against upstream `main` `e600261` unless the table says otherwise. `gx-draw-probes.patch` was rebased onto
PR #8 `622b97a` and not rebuilt since.

### F8 developer menu

`patches\devmenu.patch` is rebased onto FrightWorks `main` `114ab73`. It is **opt-in**: normal source builds do not
contain the menu, texture inspection hooks, or its test target. Apply only this patch to enable F8; no audio diagnostic
patch, audio capture, private texture pack, or generated catalogue is required.

The existing build/play wrappers replace the repository's `Play\` executable. Use an isolated checkout and preserve
running games, settings, and saves. For build-only validation, with the pinned tools/dependencies and your own supported
disc already prepared:

```powershell
git apply --check tools\debug\patches\devmenu.patch
git apply tools\debug\patches\devmenu.patch
# Rebuild the translator first if switching branches changed its source.
powershell -NoProfile -ExecutionPolicy Bypass -File tools\build-no100f.ps1 -ConfigureOnly -SkipTools -Jobs 4
$env:PATH = (Join-Path $PWD 'toolchain\llvm-mingw\bin') + ';' + $env:PATH
toolchain\CMake\bin\cmake.exe --build wiicompiled\native-build --target WiiCompiled no100f_devmenu_state_tests --parallel 4
toolchain\CMake\bin\ctest.exe --test-dir wiicompiled\native-build -R '^no100f_devmenu_state_tests$' --output-on-failure
git apply -R --check tools\debug\patches\devmenu.patch
git apply -R tools\debug\patches\devmenu.patch
```

The configure-only command does not perform the build script's final executable replacement. Removing the patch
restores source, not any executable previously built with it. Fully retranslate on the first build after applying or
removing a patch that changes native overrides; do not use `-SkipTranslate` for that build.

In a patched build, press **F8** to open the menu. The Textures or Effects tab itself is the inspector; there is no
additional tool to open. Effects inspects runtime effect textures, not gameplay-effects toggles.

- **Skip:** recorded cutscenes use the game's normal A/Confirm input; title/demo contexts use Start. Short repeated
  presses stop when the original game mode, state, or cutscene-manager pointer changes, or after ten seconds.
  The game may refuse a skip during its initial unskippable interval. Guest movie pointers and audio state are not reset.
- **Travel:** start or load a game first. Scene requests wait for normal play, player control, and an available portal,
  then submit once through the normal portal path. Only one scene/spot transfer can be pending. Waiting requests can
  be canceled; cancellation is disabled once the load starts. The 60-second scene-request timeout never clears an
  in-flight guest portal. Cross-scene saved spots wait for arrival and settling before restoring position/camera.
- **Free camera:** travel turns it off; camera application also rejects a changed scene pointer or ID.
- **Inspectors:** Textures and Effects have separate categories, widget IDs, and scene/fine filters. Reload rereads the
  catalogue. Tables scroll in both directions so long metadata and saved-spot controls remain accessible. Missing data
  and an all-filtered result have distinct messages.

The optional catalogue is `UserData\devmenu_textures.txt`, in the runtime's application-data directory. It uses tabs:

```text
id<TAB>replacement key<TAB>severity<TAB>asset<TAB>space-separated scene IDs<TAB>level<TAB>optional category
```

The first six fields describe a texture entry. A seventh value beginning with `effect` identifies an Effects entry;
leading whitespace and case are ignored, and `effect:particle` is accepted. Other entries appear in Textures.
No catalogue or replacement images are shipped with the patch. Without a catalogue, the inspector explains where to
put it and how to reload. Actual replacement highlighting requires the corresponding legitimate replacement assets.

The state tests cover invalid/busy requests, waiting, one-shot submission, arrival, cancellation, timeout, skip pulse
expiry/context cancellation, skip-control selection, and effect-category parsing; assertions stay enabled in Release.

Earlier isolated **v2** playtests verified the opening-story skip, title/demo exit, repeated h001/h002 transfers,
free-camera reset, saved-spot return, and inspector categories/filter/reload behavior. **V3** changed inspector rendering:
its separate visual check verified horizontal access to long-metadata/saved-spot/Find controls, vertical access through
20 synthetic rows, and visible all-filtered/missing-catalogue messages. Temporary test data was removed.
Those playtests used the earlier local backport checkout, not this rebased patch on current main. Do not count them as
fresh runtime verification of the final PR source. Real replacement highlighting and all-level/long-run travel
reliability remain unverified.

Requirements: Python 3 with numpy + Pillow (+ `capstone` for `dol.py`/`overrides.py`, SciPy for `creeper-frames.py`). The
`capture\` tools use ffmpeg from PATH; without one, `capture\get-ffmpeg.ps1` downloads the BtbN win64 GPL build once into
`tools\debug\local\ffmpeg` (SHA-256 checked).
