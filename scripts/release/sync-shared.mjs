// Reuse the audited terminal components without installing the full terminal on Pages.
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
for(const file of ['components/presentation-provider.tsx','components/preferences.tsx','lib/presentation.ts','lib/chart-presentation.ts','lib/chart-theme.ts','messages/en-US.json','messages/zh-CN.json']){
 const target=path.join(root,'showcase/shared',file);mkdirSync(path.dirname(target),{recursive:true});
 writeFileSync(target,readFileSync(path.join(root,'frontend',file)));
}
for(const file of ['licenses.json','snapshot.schema.json'])writeFileSync(path.join(root,'showcase/public/data',file),readFileSync(path.join(root,'data',file)));
console.log('Reused 7 terminal presentation files; copied independent data notices and schema.');
