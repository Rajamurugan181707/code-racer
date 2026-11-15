# Changelog

## 2.0 (2026-11-15)

- **Graphics.** The renderer is rewritten, with three themed worlds:
  - Sunset Coast (Easy)
  - Neon City (Medium)
  - Storm Pass (Hard): rain, lightning and wet-road reflections

  Each world has parallax layers, textured asphalt with kerbs, start lights and a waving finish flag.
- **Car.** A new car with gradient paint, window reflections, alloy wheels, brake calipers, headlight and tail-light
  glow, and underglow.
- **Effects:** a boost flame and speed lines on every correct line; floating score text; and on a crash, sparks,
  debris, smoke, skid marks and a flash. Finishing a track brings fireworks.
- **Gameplay:**
  - a score, made of a base, a typing-speed bonus, combo multipliers up to x3, a time bonus and points for cars left
  - a live typing-speed gauge
  - a best score and fastest time per track
  - a ghost car that replays your fastest run
  - a results screen with WPM, clean lines and best combo
- **Sound.** Synthesised sound effects, with an on/off toggle that is remembered. There is also a ghost-car toggle.
- **Robustness.** The frame time step can no longer go negative, and a frame that fails to draw no longer stops the
  game loop.
- **Tooling.** `build.sh`, and `tests/verify_tracks.mjs`, which checks all 90 programs (all pass), plus a README.
- **Tracks unchanged.** All 30 tracks are unchanged.
