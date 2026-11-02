/**
 * Compares the extracted source texts (src/locale/messages.json) with each translation
 * and lists the ids a translation is missing or still carries after they were dropped.
 */
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const locales = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'locale');
const ids = (file) => Object.keys(JSON.parse(readFileSync(join(locales, file), 'utf8')).translations);

const source = new Set(ids('messages.json'));
let clean = true;

for (const file of readdirSync(locales).filter((name) => /^messages\..+\.json$/.test(name))) {
  const translated = new Set(ids(file));
  const missing = [...source].filter((id) => !translated.has(id));
  const obsolete = [...translated].filter((id) => !source.has(id));
  for (const [label, list] of [['missing', missing], ['obsolete', obsolete]]) {
    if (list.length > 0) {
      clean = false;
      console.log(`${file}: ${list.length} ${label}\n  ${list.join('\n  ')}`);
    }
  }
}

if (clean) {
  console.log(`translations match the ${source.size} source texts`);
}
process.exitCode = clean ? 0 : 1;
