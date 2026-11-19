const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),ts=require('typescript');
const root=path.resolve(__dirname,'..');
module.exports=function load(file,mocks={},cache=new Map()){
 const absolute=path.isAbsolute(file)?file:path.join(root,file);if(cache.has(absolute))return cache.get(absolute).exports;
 if(absolute.endsWith('.json'))return JSON.parse(fs.readFileSync(absolute,'utf8'));
 const source=fs.readFileSync(absolute,'utf8');const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true,resolveJsonModule:true}}).outputText;
 const mod=new Module(absolute,module);mod.filename=absolute;mod.paths=Module._nodeModulePaths(path.dirname(absolute));cache.set(absolute,mod);
 mod.require=id=>{if(id in mocks)return mocks[id];if(id.endsWith('.css'))return {};if(id.startsWith('.')||id.startsWith('@/')){let target=id.startsWith('@/')?path.join(root,id.slice(2)):path.resolve(path.dirname(absolute),id);if(!path.extname(target)){const ext=['.ts','.tsx','.json'].find(e=>fs.existsSync(target+e));if(ext)target+=ext;}if(/\.(tsx?|json)$/.test(target))return load(target,mocks,cache);}return require(id)};
 mod._compile(code,absolute);return mod.exports;
};
