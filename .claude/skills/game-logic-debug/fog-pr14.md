# i004 floor fog flicker at 60 fps — PR #14 `fix/fog-fps60` `1864646` (2026-10-24)

- Symptom: "Mind your Manors Part 1" (`i004`), floor fog puffs flash brighter for single frames, worst at the grate near the
  start. On `main` too; only with `[video] fps60` (6 s at spawn: 64/276 frames flash with fps60, 3/171 without); Dolphin smooth.
- Repro: `mkhip.py i004 --spot spot1` (grate view, monsters moved off-map), record 6 s, `flashcount.py`.
- How it was found:
  1. `fogstat-probes.patch` (per-frame blended draw stats): the fog batch kept the same triangle count, but its screen coverage
     spiked for single frames, always on the first two quads in the list.
  2. postool `trace` of the fog system's list: those two particles were replaced every frame; their memory then held torch-flame
     particles.
  3. `parsys.py` on dumps: pool 2000/2000 at 60 fps (torch system 1442 particles) vs ~1560 at 30 fps (torches 954).
- Cause: torches/candles use emitters with interval 0 → emit every call of the per-frame update `0x800C4AAC`. At 60 fps that is
  twice the particles; the pool fills; the allocator steals the newest particles of the lowest-priority system (the fog,
  priority 0), which respawn at random spots → a puff near the camera flashes for one frame.
- Fix: native `0x800C4AAC` (`hle/no100f_particles.cpp`, 41 lines): with fps60, per emitter accumulate `dt`, call the game's emit
  once the sum reaches 0.75/30 s with the summed `dt`. Particles still move every frame. Without fps60 unchanged.
- Result: 49 → 0 flash frames (PR clip); pool ~1560 at 60 fps like 30 fps. `births` per emitter, path 1 (this update): ~1.0x of
  30 fps in `i004`, `i001`, `e001`, `h002` (torches 419.5/s both). Smoke `i001`, `h001`, `i004`. Human visual: fixed. PR body has
  before/after `.mp4`.

Not fixed (path 2, next): `fn_800C5C0C` ("emit with overrides", ~90 entity callers). Continuous users still ~2x at 60 fps:
`PAREMIT_SMALL_VAN_PUFF` 2.0x (`i004`, `h002`), `PAREMIT_CHAND_CANDLE` 1.4–2.4x (`i001`, `i004`), `PAREMIT_FIREWORKS_TRAIL` 2.5x
(`h002`). Not near pool exhaustion in the levels measured. Rain/snow (`PAREMIT_RAIN`/`SNOW`, code-driven) not measured. It also
fires one-shot bursts, so the same accumulate-dt trick must not drop or delay those: plan is "once per 30 Hz step of game time"
only for emitters with interval < 1/30, keyed per emitter.
