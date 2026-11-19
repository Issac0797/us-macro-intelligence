import test from 'node:test';
import assert from 'node:assert/strict';
import {transform,spread,correlation,readWorkspace,defaults,units} from '../lib/research.ts';
const series=(points,extra={})=>({id:'TEST_ONLY',units:'Index',frequency:'monthly',observations:points.map(([date,value])=>({date,value})),...extra});
test('calendar gaps are not bridged; zero denominators and missing values stay null',()=>{
 const s=series([['2020-01-01',100],['2020-03-01',120],['2021-01-01',110],['2021-02-01',null],['2021-03-01',0]]);
 assert.equal(transform(s,'mom')[1].value,null);
 assert.ok(Math.abs(transform(s,'yoy')[2].value-10)<1e-10);
 assert.equal(transform(s,'yoy')[4].value,null);
 assert.equal(transform(s,'raw')[3].value,null);
});
test('daily yield changes use consecutive observations and percentage points, never inflation growth',()=>{
 const s=series([['2020-01-02',1],['2020-01-03',null],['2020-01-06',2]],{frequency:'daily',units:'Percent'});
 assert.deepEqual(transform(s,'absolute_change').map(p=>p.value),[null,null,null]);
 assert.equal(units(s,'absolute_change'),'pp');assert.throws(()=>transform(s,'yoy'));
});
test('spreads use exact shared dates; Pearson statistics disclose paired sample count',()=>{
 const a=series([['2020-01-01',1],['2020-02-01',2],['2020-03-01',3],['2020-04-01',4]]);
 const b=series([['2020-01-01',2],['2020-02-01',4],['2020-03-01',6]]);
 assert.deepEqual(spread(a,b).map(p=>p.value),[-1,-2,-3,null]);
 assert.deepEqual(correlation(a.observations,b.observations),{n:3,value:1});
 assert.equal(correlation(a.observations,series([['2020-01-01',0],['2020-02-01',0],['2020-03-01',0]]).observations).value,null);
});
test('browser configuration rejects unknown series, incompatible versions and invalid ranges',()=>{
 assert.deepEqual(readWorkspace('{broken',[]),defaults);
 assert.deepEqual(readWorkspace(JSON.stringify({...defaults,first:'UNREVIEWED'}),['CPIAUCSL','CPILFESL']),defaults);
 assert.deepEqual(readWorkspace(JSON.stringify({...defaults,start:'2025-01-01',end:'2020-01-01'}),['CPIAUCSL','CPILFESL']),defaults);
 assert.deepEqual(readWorkspace(JSON.stringify({...defaults,linked:false}),['CPIAUCSL','CPILFESL']),{...defaults,linked:false});
});
