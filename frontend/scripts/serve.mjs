/**
 * Starts a dev server per language: German on 4200, English on 4201 under /en/,
 * which the German one proxies, so the switch works on one origin as behind nginx.
 */
import { spawn } from 'node:child_process';

const servers = [
  ['de', ['ng', 'serve', '--configuration', 'languages']],
  ['en', ['ng', 'serve', '--configuration', 'en']],
].map(([language, command]) => {
  const child = spawn('npx', command, { shell: true, stdio: ['inherit', 'pipe', 'pipe'] });
  for (const stream of [child.stdout, child.stderr]) {
    stream.on('data', (chunk) => {
      for (const line of chunk.toString().split(/\r?\n/).filter(Boolean)) {
        console.log(`[${language}] ${line}`);
      }
    });
  }
  child.on('exit', (code) => {
    servers.forEach((other) => other.kill());
    process.exitCode = code ?? 0;
  });
  return child;
});
