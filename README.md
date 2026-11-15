# Code Racer

**Play:** https://code-racer.netlify.app

Code Racer is a browser game: type a program line by line, and each correct line drives your car to the next
checkpoint. A bug crashes it.

- **Tracks:** 30 tracks (10 Easy, 10 Medium, 10 Hard), each in Python, C and Java.
- **Worlds:** each tier has its own world, drawn live on a canvas:
  - Easy: Sunset Coast (sun, palms, dusk sky)
  - Medium: Neon City (skyline with lit windows, neon signs, street lamps)
  - Hard: Storm Pass (rain, lightning, wet-road reflections)
- **Car and effects:** a detailed sports car with alloy wheels, underglow and lights. Each correct line fires a
  boost flame, with speed lines and floating score text. Crashes bring sparks, debris, skid marks and a screen flash.
  Finishing brings fireworks and confetti.
- **Scoring:** each line scores 100 plus a typing-speed bonus. Lines right first time build a combo up to x3.
  A finished track adds a time bonus and 150 points for each car left.
- **Ghost car:** replays your fastest finished run on that track.
- **Sound:** sound effects are made in the browser with Web Audio.
- **Real compilers:** lines typed differently from the track's version are compiled and run for real on the free
  Wandbox service (Python 3.13, gcc 13.2, OpenJDK 22). If Wandbox is unreachable, the game falls back to its
  built-in checker.
- **Saved progress:** progress, best scores and ghost runs stay in your browser (localStorage).
- **Accessibility:** all text is white on dark, and motion effects are reduced when the system asks for reduced
  motion.

## Files

| File | Role |
|---|---|
| `code-racer.html` | Game source (artifact format: no doctype) |
| `build.sh` | Builds `index.html` and `site/index.html` from the source (runs the track checker first) |
| `tests/verify_tracks.mjs` | Checks all 90 programs with the built-in checker, then compiles and runs each with local python3 / gcc / javac |
| `server/` | Optional self-hosted code runner (Docker, `render.yaml`). Not deployed; the live game uses Wandbox |

## Commands

```bash
node tests/verify_tracks.mjs        # checker + real runs of all 90 programs
./build.sh                           # build site/index.html
python3 -m http.server 8613 --directory site
npx -y netlify-cli deploy --prod --dir site --site 8eb74109-f4a8-4ed6-a293-95df27dba600 --no-build
```
