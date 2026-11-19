import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
function run(args){const npm=process.platform==='win32'?'npm.cmd':'npm';const r=spawnSync(npm,args,{cwd:root,stdio:'inherit',shell:process.platform==='win32',env:{...process.env,NEXT_TELEMETRY_DISABLED:'1'}});if(r.status!==0)process.exit(r.status||1);}
// Complete installation from a committed lockfile; no source download, API key or DB.
run(['ci','--prefix','showcase','--no-fund','--no-audit']);
run(['run','build','--prefix','showcase']);
const check=spawnSync(process.execPath,['scripts/release/check-static.mjs'],{cwd:root,stdio:'inherit'});if(check.error)throw check.error;process.exit(check.status??1);
