// Bundles index.html into a single self-contained HTML file that opens
// directly in a browser via file:// (no server needed).
//
//   npm install esbuild
//   node build-standalone.mjs
//
// Output: strawberry-matcha-latte.html
import { build } from 'esbuild';
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const root = import.meta.dirname;
const html = readFileSync(join(root, 'index.html'), 'utf8');

// 1) pull out the module script + strip the importmap
const body = html.match(/<script type="module">([\s\S]*?)<\/script>/)[1];
const shell = html
  .replace(/<script type="importmap">[\s\S]*?<\/script>\s*/, '')
  .replace(/<script type="module">[\s\S]*?<\/script>/, '<!--BUNDLE-->');

// 2) rewrite bare specifiers to the vendored files
const entry = body
  .replace(/from 'three\/addons\//g, `from '${root}/vendor/addons/`)
  .replace(/from 'three'/g, `from '${root}/vendor/three.module.js'`);

const tmp = join(mkdtempSync(join(tmpdir(), 'sml-')), 'entry.mjs');
writeFileSync(tmp, entry);

// 3) bundle to one IIFE (addons import bare 'three' -> alias to vendor)
const result = await build({
  entryPoints: [tmp],
  bundle: true,
  format: 'iife',
  minify: true,
  write: false,
  alias: { three: join(root, 'vendor/three.module.js') },
});
const js = result.outputFiles[0].text;

// 4) inline as a classic script so it runs over file://
const out = shell.replace('<!--BUNDLE-->', `<script>\n${js}\n</script>`);
writeFileSync(join(root, 'strawberry-matcha-latte.html'), out);
console.log('Wrote strawberry-matcha-latte.html (%d KB)', Math.round(out.length / 1024));
