import test from 'node:test';
import assert from 'node:assert/strict';
import {applyWorkspaceLink,restoreWorkbench,commonDomain,exactCursor,chartExport,exportCsv,validDate,visiblePoints} from '../lib/workbench.ts';
import {rangeStart} from '../lib/explorer.ts';
import {searchPublic} from '../lib/search.ts';
import {readFileSync} from 'node:fs';
const snapshot=JSON.parse(readFileSync(new URL('../public/data/snapshot.json',import.meta.url)));
test('explorer links preserve a reviewed series, compatible transform, comparator and snapshot-relative range', () => {
 const config = restoreWorkbench(null, snapshot.series);
 const linked = applyWorkspaceLink(config, new URLSearchParams('series=CPILFESL&transform=mom&compare=CPIAUCSL&range=3Y'), snapshot.series);
 assert.deepEqual(linked.panels.slice(0, 2), [{ series: 'CPILFESL', transform: 'mom' }, { series: 'CPIAUCSL', transform: 'yoy' }]);
 const end = snapshot.series.find(item => item.id === 'CPILFESL').coverage.end;
 assert.equal(linked.end, end);
 assert.equal(linked.start, rangeStart(end, '3Y'));
 assert.equal(config.panels[0].series, 'CPIAUCSL');
 const invalid = applyWorkspaceLink(config, new URLSearchParams('series=CPILFESL&transform=unknown&compare=PCE&range=999Y'), snapshot.series);
 assert.equal(invalid.panels[0].transform, 'yoy');
 assert.deepEqual(invalid.panels.slice(1), config.panels.slice(1));
 assert.equal(invalid.start, config.start);
 assert.equal(applyWorkspaceLink(config, new URLSearchParams('series=PCE&compare=DGS10'), snapshot.series), config);
});
test('snapshot-relative presets clamp leap days and offer full native coverage', () => {
 assert.equal(rangeStart('2024-02-29', '1Y'), '2023-02-28');
 assert.equal(rangeStart('2024-02-29', 'ALL'), '');
});
test('legacy two-panel configuration migrates without losing selected series, date window or units',()=>{
 const c=restoreWorkbench(null,snapshot.series,{version:1,first:'DGS10',second:'DGS2',transform:'absolute_change',start:'2023-01-01',end:'2024-01-01',linked:false});
 assert.equal(c.panels.length,4);assert.deepEqual(c.panels.slice(0,2),[{series:'DGS10',transform:'absolute_change'},{series:'DGS2',transform:'absolute_change'}]);assert.equal(c.linked,false);assert.equal(c.start,'2023-01-01');
});
test('saved four-panel configuration rejects unreviewed indicators and rate growth transformations',()=>{
 const c=restoreWorkbench(null,snapshot.series);c.panels[0]={series:'UNREVIEWED',transform:'raw'};assert.equal(restoreWorkbench(JSON.stringify(c),snapshot.series).panels[0].series,'CPIAUCSL');
 c.panels[0]={series:'DGS10',transform:'yoy'};assert.equal(restoreWorkbench(JSON.stringify(c),snapshot.series).panels[0].series,'CPIAUCSL');
});
test('invalid calendar days and inverted windows cannot restore a saved research range',()=>{
 assert.equal(validDate('2024-02-29'),true);assert.equal(validDate('2026-02-29'),false);assert.equal(validDate('2026-99-01'),false);
 const c=restoreWorkbench(null,snapshot.series);c.start='2026-01-01';c.end='2020-01-01';assert.equal(restoreWorkbench(JSON.stringify(c),snapshot.series).start,'2021-01-01');
});
test('four charts share a UTC domain across monthly and daily coverage without resampling',()=>{
 const d=commonDomain(snapshot,'2021-01-01','2026-11-16');assert.deepEqual(d,[Date.parse('2021-01-01T00:00:00Z'),Date.parse('2026-11-16T00:00:00Z')]);
 const a=commonDomain(snapshot,'2040-01-01','2041-01-01');assert.ok(a[0]>Date.parse(snapshot.series[0].coverage.end));
});
test('mixed-frequency cursor never substitutes a nearest monthly observation and preserves numeric zero',()=>{
 const p=[{date:'2020-01-01',value:0},{date:'2020-02-01',value:null}];assert.deepEqual(exactCursor(p,Date.parse('2020-01-15')),{date:'2020-01-15',value:null,hasObservation:false});assert.equal(exactCursor(p,Date.parse('2020-01-01')).hasObservation,true);assert.equal(exactCursor(p,Date.parse('2020-01-01')).value,0);assert.equal(exactCursor(p,Date.parse('2020-02-01')).hasObservation,false);
});
test('JSON exports retain snapshot basis and agency terms while leaving an empty range empty',()=>{
 const data=chartExport(snapshot,snapshot.series[0],'yoy',[],'%');assert.equal(data.is_live,false);assert.equal(data.snapshot_generated_at,snapshot.generated_at);assert.deepEqual(data.displayed_observations,[]);assert.ok(!('observations' in data.source));assert.match(data.data_license,/not relicensed under MIT/);assert.equal(exportCsv(data).split('\r\n').length,1);
});
test('CSV exports retain true dates, nulls, units and provenance and escape quoted source notices',()=>{
 const source={...snapshot.series[0],notice:'Quoted "notice", not MIT'};const data=chartExport(snapshot,source,'raw',[{date:'2020-01-01',value:null}],source.units);const csv=exportCsv(data);assert.match(csv,/2020-01-01/);assert.ok(csv.includes('""'));assert.ok(csv.includes('"Quoted ""notice"", not MIT"'));assert.ok(csv.includes(source.id));assert.ok(csv.includes(snapshot.generated_at));
});
test('Ctrl+K search matches aliases and Chinese metadata and only returns public routes or reviewed series',()=>{
 const english=searchPublic('CPIAUCSL',snapshot.series,false);assert.equal(english[0].url,'/workspace/?series=CPIAUCSL');assert.ok(searchPublic('失业率',snapshot.series,false).some(r=>r.url.endsWith('UNRATE')));assert.equal(searchPublic('PCEPILFE',snapshot.series,false).length,0);assert.equal(searchPublic('http://private.invalid',snapshot.series,false).length,0);
});
test('exported observations respect the actual zoom bounds while preserving nulls and native dates',()=>{
 const points=[{date:'2020-01-01',value:1},{date:'2020-02-01',value:null},{date:'2020-03-01',value:3}];
 assert.deepEqual(visiblePoints(points,Date.parse('2020-01-15'),Date.parse('2020-03-01')),points.slice(1));assert.deepEqual(visiblePoints(points,Date.parse('2030-01-01'),Date.parse('2031-01-01')),[]);
});
