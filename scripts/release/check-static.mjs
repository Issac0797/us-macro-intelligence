import {readFileSync,existsSync,readdirSync,statSync} from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const out=path.join(root,'showcase/out');
const routes=['','inflation','labor','yield-curve','workspace','analytics','fed','sources','about','business-cycle'];
for(const route of routes)assert.ok(existsSync(path.join(out,route,'index.html')),`Missing physical route: ${route}`);
assert.ok(existsSync(path.join(out,'404.html')),'Missing real 404 page');
const snapshot=JSON.parse(readFileSync(path.join(out,'data/snapshot.json')));
const registry=JSON.parse(readFileSync(path.join(root,'data/licenses.json')));
assert.equal(snapshot.is_live,false);
assert.deepEqual(snapshot.series.map(s=>s.id).sort(),registry.series.filter(s=>s.status==='approved'&&s.permission==='public-domain').map(s=>s.id).sort());
for(const s of snapshot.series){assert.equal(s.coverage.count,s.observations.length);assert.equal(s.coverage.start,s.observations[0].date);assert.equal(s.coverage.end,s.observations.at(-1).date);assert.equal(s.source_url,registry.series.find(r=>r.id===s.id).source_url);}
const secrets=[/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/,/\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b/,/[A-Z]:[\\/]Users[\\/][^\s"'<>]+/i,/postgres(?:ql)?(?:\+psycopg)?:\/\/[^\s/:]+:[^\s@]+@/i];
let files=0,links=0;
function walk(dir){for(const name of readdirSync(dir)){const p=path.join(dir,name);if(statSync(p).isDirectory()){walk(p);continue;}files++;
 if(/\.(?:html|js|json|txt|css)$/.test(p)){
  const source=readFileSync(p,'utf8');for(const rule of secrets)assert.ok(!rule.test(source),`Sensitive content in ${path.relative(out,p)}`);
  // The project's backend endpoint must never appear in a public browser bundle.
  assert.ok(!source.includes('/api/v1/'),`Local terminal API reference in ${path.relative(out,p)}`);
  assert.ok(!/https?:\/\/(?:localhost|127\.0\.0\.1)(?::\d+)?\/api\b/.test(source),`Loopback API request in ${p}`);
  if(p.endsWith('.html'))for(const m of source.matchAll(/(?:href|src)="([^"#?]+)(?:[?#][^"]*)?"/g)){
   const url=m[1].replaceAll('&amp;','&');if(/^(?:https?:|data:|mailto:|tel:)/.test(url))continue;
   const target=path.resolve(url.startsWith('/')?out:path.dirname(p),'.'+(url.startsWith('/')?url:'/'+url));
   assert.ok(target.startsWith(out+path.sep)||target===out,'Path traversal');
   assert.ok(existsSync(target)||existsSync(path.join(target,'index.html')),`Broken generated link: ${url} in ${p}`);links++;
  }
 }
}}
walk(out);
assert.ok(existsSync(path.join(out,'_headers')));
for(const file of ['licenses.json','snapshot.schema.json','third-party-notices.txt'])assert.ok(existsSync(path.join(out,'data',file)),`Missing public notice ${file}`);
console.log(`PASS: ${routes.length} physical routes, real 404, ${files} output files, ${links} links, snapshot whitelist and artifact secret scan.`);
