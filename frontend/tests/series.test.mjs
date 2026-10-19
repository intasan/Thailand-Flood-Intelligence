import {test} from 'node:test';
import assert from 'node:assert/strict';
import {seriesPlot,seriesCsv} from '../lib/series.mjs';
const row=(minute,value)=>({observed_at:`2020-01-01T00:${String(minute).padStart(2,'0')}:00Z`,value,unit:'m',metadata:{timestamp_status:'TEST_ONLY'}});
test('missing interval splits the line without inventing zero measurements',()=>{
 const plot=seriesPlot([row(0,1),row(10,2),row(40,3)]);
 assert.deepEqual(plot.segments.map(s=>s.length),[2,1]);assert.equal(plot.points.length,3);
});
test('invalid measurement breaks a line even when time spacing is short',()=>{
 const plot=seriesPlot([row(0,1),row(5,null),row(10,2)]);
 assert.deepEqual(plot.segments.map(s=>s.length),[1,1]);assert.deepEqual(plot.points.map(p=>p.value),[1,2]);
});
test('zero and negative station MSL values remain valid; constant series scales safely',()=>{
 const zero=seriesPlot([row(0,0),row(10,0)]);assert.equal(zero.points.length,2);assert.ok(zero.points.every(p=>Number.isFinite(p.y)));
 assert.equal(seriesPlot([row(0,-.5)]).points[0].value,-.5);
});
test('duplicate timestamps and invalid domains rejected instead of misleading lines',()=>{
 assert.throws(()=>seriesPlot([row(0,1),row(0,2)]));
 assert.throws(()=>seriesPlot([row(0,1)],{start:'2020-01-02T00:00:00Z',end:'2020-01-03T00:00:00Z'}));
});
test('CSV preserves raw numeric values/provenance, escapes text and leaves missing values blank',()=>{
 const series={station:{id:'=TEST_ONLY',vertical_datum:'TEST',source_url:'https://example.invalid'},results:[{...row(0,-.25),raw_sha256:'test-only',metadata:{source_quality_flag:'N',timestamp_status:'TEST_ONLY'}},row(10,null)]};
 const csv=seriesCsv(series);
 assert.ok(csv.includes('"\'=TEST_ONLY"'));assert.ok(csv.includes('"-.25"')||csv.includes('"-0.25"'));assert.ok(csv.includes('"test-only"'));
 assert.ok(csv.includes('"value"'));assert.ok(csv.split('\r\n')[2].includes(',"","m",'));
});
