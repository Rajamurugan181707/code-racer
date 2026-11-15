// Verifies every track: each expected line passes the built-in checker, some wrong lines
// fail it, and every full program compiles and prints the track's expected output
// when run with the local python3 / gcc / javac.
//   node tests/verify_tracks.mjs            (checker + real runs)
//   node tests/verify_tracks.mjs --no-run   (checker only)
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import {execFileSync} from 'node:child_process';

const html = fs.readFileSync(new URL('../code-racer.html', import.meta.url), 'utf8');
const js = html.split('<script>')[1].split('</script>')[0];
const engine = js.slice(0, js.indexOf('/* ---------------- real execution'));
const ctx = {};
vm.runInNewContext(engine + '\nthis.LEVELS=LEVELS;this.buildProgram=buildProgram;this.diagnose=diagnose;this.outputFor=outputFor;', ctx);
const {LEVELS, buildProgram, diagnose, outputFor} = ctx;
const run = !process.argv.includes('--no-run');
const clean = s => s.replace(/\r/g, '').split('\n').map(x => x.replace(/\s+$/, '')).join('\n').replace(/\n+$/, '');
let fails = 0, checked = 0, runs = 0;
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'racer-'));

for (const [i, lvl] of LEVELS.entries()) for (const lang of ['py', 'c', 'java']) {
  const lines = buildProgram(lvl, lang);
  for (const l of lines) if (!l.given) {
    checked++;
    if (!diagnose(l.expect, l.expect, lang).ok) { fails++; console.log(`FAIL checker accepts-own ${i + 1} ${lang}: ${l.expect}`); }
    const broken = l.expect.replace(/[;)]$/, '');
    if (broken !== l.expect && diagnose(broken, l.expect, lang).ok) { fails++; console.log(`FAIL checker accepted broken ${i + 1} ${lang}: ${broken}`); }
  }
  if (!run) continue;
  const src = lines.map(l => l.given ? l.code : l.ind + l.expect).join('\n') + '\n';
  const dir = fs.mkdtempSync(path.join(tmp, `${i}-${lang}-`));
  let out;
  try {
    if (lang === 'py') { fs.writeFileSync(path.join(dir, 'main.py'), src); out = execFileSync('python3', ['main.py'], {cwd: dir, timeout: 20000}).toString(); }
    if (lang === 'c') { fs.writeFileSync(path.join(dir, 'main.c'), src); execFileSync('gcc', ['-w', 'main.c', '-o', 'race', '-lm'], {cwd: dir}); out = execFileSync('./race', {cwd: dir, timeout: 20000}).toString(); }
    if (lang === 'java') { fs.writeFileSync(path.join(dir, 'Main.java'), src); execFileSync('javac', ['Main.java'], {cwd: dir}); out = execFileSync('java', ['Main'], {cwd: dir, timeout: 20000}).toString(); }
    runs++;
    if (clean(out) !== clean(outputFor(lvl, lang))) { fails++; console.log(`FAIL output ${i + 1} ${lvl.name} ${lang}:\n  got  ${JSON.stringify(clean(out))}\n  want ${JSON.stringify(outputFor(lvl, lang))}`); }
  } catch (e) { fails++; console.log(`FAIL run ${i + 1} ${lvl.name} ${lang}: ${String(e.stderr || e.message).slice(0, 300)}`); }
}
fs.rmSync(tmp, {recursive: true, force: true});
console.log(`${LEVELS.length} tracks, ${checked} typed lines checked, ${runs} programs run, ${fails} failures`);
process.exit(fails ? 1 : 0);
