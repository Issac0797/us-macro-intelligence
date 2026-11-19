import test from 'node:test';
import assert from 'node:assert/strict';
import {template,calc,chartCsv,csv} from '../lib/workspace-utils.ts';

test('templates preserve reproducible identifiers and explicit native pipeline parameters',()=>{
 for(let i=0;i<4;i++)assert.deepEqual(template(i),template(i));
 const labor=template(1);
 assert.deepEqual(labor.lines[1].calculations.map(s=>[s.transform,s.window]),[['absolute_change',12],['moving_average',3]]);
 assert.equal(labor.lines[1].axis,'right');
 assert.equal(template(3).frequency,'quarterly');
 assert.equal(template(2).lines[2].subtract_series_id,'DGS2');
});

test('CSV preserves missing values and the historical calculation and version metadata',()=>{
 const configuration=template(0);configuration.data_mode='vintage';configuration.as_of='2023-06-15';
 const first=configuration.lines[0];first.display_name='Core "PCE", YoY';
 const text=chartCsv({configuration,series:[{key:first.key,display_name:first.display_name,units:'Percent',provenance:{native_frequency:'monthly',dependency_fingerprint:'a'.repeat(64),retrieved_at:'2026-11-12T12:00:00Z'},points:[{date:'2023-05-31',value:null,observation_dates:['2023-05-01'],effective_vintage:'2023-06-01',source_versions:['2023-06-01']}]}]});
 assert.ok(text.includes('"effective_vintage","source_versions","dependency_fingerprint"'));
 assert.ok(text.includes('"vintage","2023-06-15"'));
 assert.ok(text.includes('"Core ""PCE"", YoY","","Percent"'));
 assert.ok(text.includes('"2023-05-01","2023-06-01","2023-06-01"'));
 assert.ok(text.includes('"transform""'));
 assert.equal(text.split('\r\n').length,2);
});

test('CSV quotes user labels including commas, quotes and line breaks',()=>{
 assert.equal(csv([['a,b','"quoted"','line\nbreak',null]]),'"a,b","""quoted""","line\nbreak",""');
});

test('CSV explicitly records unavailable historical series rather than silently omitting them',()=>{
 const configuration=template(2);configuration.data_mode='vintage';configuration.as_of='2023-06-15';
 const line=configuration.lines[0];
 const text=chartCsv({configuration,series:[{key:line.key,display_name:line.display_name,units:null,points:[],provenance:{status:'HISTORICAL_VINTAGE_UNAVAILABLE'}}]});
 assert.equal(text.split('\r\n').length,2);
 assert.ok(text.includes('"DGS2"'));
 assert.ok(text.endsWith('"HISTORICAL_VINTAGE_UNAVAILABLE"'));
});
