# Levels and scenes

Every playable scene is one `.HIP` file. Its ID (`i004`) is what `-Boot`, `BOOT=`, `mkhip.py`, `births-run.ps1` and the
logs (`[dvdread] ...\I0\i004.HIP`) use. The file sits in `Disc/DATA/files/<letter>0/` (`MN/` for `mnu3`/`mnu4`;
`boot.HIP` and `font.HIP` at the top). A bad boot ID crashes the game ("Missing indirect jump target").

**Source: the game itself.** `python tools\debug\game\levels.py` reads the level table in `game/main.dol` and checks it
against the disc. `levels.py i004` prints a scene's level, part and area; `--md` regenerates the table below. Part numbers
are the order the game lists the scenes in (matches play order where checked: `i001` → `i020` on foot).

The letter is the **area**, not the level: `i` = 1st Floor of the manor, `c` = Cliffs & Caves. Mappings that guess levels
from the letter (community lists before this table was read) put e.g. "Mind Your Manors!" at `c005`; it is `i004`-`i006`.

## Level table (from `main.dol`)

| # | Level | Area | Scenes (part 1, 2, ...) | Snacks | Tokens |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | The Mystery Machine | Hub | `h001`, `h002`, `h003` | 118 | 1 |
| 2 | On Edge in the Hedge! | Hedge Maze | `e001`, `e002`, `e003`, `e004` | 371 | 2 |
| 3 | It's a Mean Greenhouse, Scooby! | Hedge Maze | `e005`, `e006` | 143 | 0 |
| 4 | Chills & Spills on Haunted Hill! | Hedge Maze | `e007`, `e008`, `e009` | 309 | 0 |
| 5 | Scared Stiff at Skull Cliff! | Cliffs & Caves | `c001`, `c002`, `c003`, `c004` | 394 | 0 |
| 6 | Misbehavin'? Cause a Cave In | Cliffs & Caves | `c005`, `c006`, `c007` | 257 | 1 |
| 7 | A Tight Spot for a Grave Plot! | Cemetery | `g001`, `g002` | 116 | 1 |
| 8 | A One Way Trip to the Crypt! | Cemetery | `g003`, `g004`, `g005`, `g006` | 224 | 1 |
| 9 | Gloom & Doom Down in the Tomb! | Cemetery | `g007`, `g008`, `g009` | 264 | 1 |
| 10 | Shock on the Dock! | Fishing Village | `f001`, `f003` | 154 | 0 |
| 11 | Fishy Clues for Scooby-Doo? | Fishing Village | `f004`, `f005`, `f006`, `f007` | 386 | 2 |
| 12 | Fear on the Pier! | Fishing Village | `f008`, `f009`, `f010` | 202 | 0 |
| 13 | Coast for Some Ghosts! | Lighthouse | `l011`, `l013`, `l014` | 373 | 2 |
| 14 | Going Down Witch Way? | Lighthouse | `l015` | 121 | 0 |
| 15 | Lighthouse Fright House! | Lighthouse | `l017`, `l018`, `l019` | 269 | 0 |
| 16 | Wreck on the Deck! | Shipwreck | `w020`, `w021`, `w022` | 268 | 1 |
| 17 | Aghast by the Mast! | Shipwreck | `w023`, `w025`, `w026` | 375 | 1 |
| 18 | Shiver Your Timbers, Scooby! | Shipwreck | `w027`, `w028` | 117 | 0 |
| 19 | Clamor in the Manor! | 1st Floor | `i001`, `i020`, `i021`, `i003` | 220 | 1 |
| 20 | Mind Your Manors! | 1st Floor | `i004`, `i005`, `i006` | 228 | 1 |
| 21 | All Scares Upstairs! | Attic & Balconies | `r001`, `r020`, `r021`, `r003` | 390 | 1 |
| 22 | Don't Look Down, Scooby-Doo! | Attic & Balconies | `r004`, `r005`, `r006` (not on disc) | 163 | 0 |
| 23 | Panic in the Attic! | Tower | `o001`, `o002`, `o003`, `o004` | 342 | 2 |
| 24 | A Dark and Stormy Knight! | Tower | `o005`, `o006`, `o008` | 240 | 0 |
| 25 | Who's Yella' in the Cellar? | Cellars | `b001`, `b002`, `b003`, `b004` | 205 | 1 |
| 26 | Creepy Crawlies in the Hallways | Secret Passages | `p001`, `p002`, `p003` | 165 | 0 |
| 27 | Gusts Abound Underground | Secret Passages | `p004`, `p005` | 110 | 0 |
| 28 | Little Lab of Horrors | Super Secret Lab | `s001`, `s002`, `s003` | 160 | 2 |
| 29 | Mastermind Unmasked! | Super Secret Lab | `s004`, `s005` | 64 | 0 |

Snacks and tokens (monster tokens; they add up to the 21 "Monster Token" flags) are the level's totals.

## Other scenes and oddities

| Scene | What it is | How we know |
| --- | --- | --- |
| `h001` | Mystic Manor front yard hub: intro, groundskeeper, game-finish texts, portals `FROM e001/f001/i001/...` | asset names; booted |
| `h002` | Mystic Playground hub: tutorial texts, portals `TO b001/c001/e001/f001/g001/...` | asset names; booted |
| `h003` | Monster Gallery (monster names, episode and trivia texts) | asset names |
| `s006` | Ending: `OUTTRO` cutscene, `BACK TO HUB` portal; not in the level table | asset names |
| `mnu3` / `mnu4` | Title / memory-card menus, in-game menu (`mnu3 start group`, `mnu4 xtocontinue` in `main.dol`) | strings |
| `boot`, `font` | Global assets (shared particle emitters `PAREMIT_*`, music/SFX) and fonts; not scenes | |
| `r006` | Listed in the level table, not on the disc | `levels.py` |
| "Cower in the Tower!" | Title string in `main.dol` that no table uses (Tower level is "Panic in the Attic!") | strings |

Boss rooms (developer readme quoted on The Cutting Room Floor; each is its level's last scene): Black Knight `o008`, Green
Ghost `g009`, Redbeard `w028`, Mastermind `s005`.

## Scenes for testing

What each scene has been used for, and what it is good for. Add a line when a scene helps an investigation.

| Scene | Use | Notes |
| --- | --- | --- |
| `i001` | Curtains (#6), foyer light shafts (#9), chandelier candles (entity emitter, PR #15), `I001 CANDLES` + sparkles (per-frame emitters, #14) | Fireplace room `i020` is reached on foot |
| `i004` | Ghost monsters (#8 regression), floor fog at the grate (#14: `mkhip.py i004 --spot spot1`), torches + candles + van puff + smoke pits: the busiest particle scene measured (pool near 2000 at 60 fps before #14) | `i003` is behind a snack gate: boot `i004` directly |
| `e001` | #2 deterministic trigger (walk-up / camera turn); leaves blowing (5.7 units/s, a good speed check), pit smoke | |
| `g001` | #2 trigger; candles + fog | |
| `h001` | Smoke test; holiday events (chimney smoke, Halloween bats over the porch, snow); fountains, leaves, fireworks | Boot can stick on the intro→manor cutscene (seen twice at 60 fps on 2026-10-24, also on `main`): retry |
| `h002` | #2 trigger; music crackle (#11); holiday fireworks/snow; van puff, firework bursts and trails (#15) | Without #12/#13 both hubs fire New Year's fireworks every load (`patches/real-date.patch` silences them) |
| `p003` | `FLAMER_EMITTER`s with a 0.03 s interval: timer-driven emission just under one 30 Hz frame | Not tested yet |

### Where to find an effect

From particle emitter asset names per scene (`PARE`, `boot.HIP` excluded). Rain/snow in the hubs are holiday or
code-driven and come from `boot.HIP`.

| Effect | Scenes |
| --- | --- |
| Torches | `b002` `b003` `c001`-`c007` `i004` `p001`-`p005` |
| Candles | `g001`-`g007` `g009` `i001` `i003` `i004` `i006` `i020` `i021` `p003` |
| Fog | `e001`-`e009` `g001`-`g004` `g006`-`g009` `i004` |
| Rain | `o005` `o008` `w021` (not tested at 60 fps) |
| Smoke | `e001`-`e003` `e008` `f001` `f003`-`f005` `g009` `i001` `i003` `i004` `i006` `i020` `i021` `o001`-`o004` `o008` `r001` `r020` `w026` |
| Fire | `e004` `e005` `e009` `g004` `i021` `o001` `o004` `o005` `p003` `r020` |
| Leaves | `e001`-`e009` `h001` |
| Fountains | `e004` `e006` `h001` |
| Water / splash | `e006` `i003` |
| Bubbles / acid | `s002` `s004` / `s002` |

## Sources

- `game/main.dol`: area table `0x801D6428`, level table `0x801D651C` (`levels.py`).
- Asset names: `audio/hip.py` or the `assets()` walker in `game/mkhip.py`.
- [The Cutting Room Floor](https://tcrf.net/Scooby-Doo!_Night_of_100_Frights_(GameCube,_PlayStation_2,_Xbox)): boss
  room IDs (developer readme), unused debug-menu portals (`l001`, `w001`: not on this disc).
- [HDBSD/SDNo100F-Tools `Game.lua`](https://github.com/HDBSD/SDNo100F-Tools/blob/main/SDnoOF/Game.lua): community level
  selector's scene list (includes `f011`, not on this disc).
- [Industrial Park](https://github.com/igorseabra4/IndustrialPark): HIP editor/viewer.
