import {test} from 'node:test';
import assert from 'node:assert/strict';
import {pointHash,readPointHash} from '../lib/share.mjs';
test('share fragment preserves chosen location with explicit coordinate order',()=>{
 assert.deepEqual(readPointHash(pointHash(13.7563,100.5018)),{lat:13.7563,lon:100.5018});
 assert.deepEqual(readPointHash(pointHash(0,0)),{lat:0,lon:0});
});
test('ambiguous or invalid share fragments never move the selected location',()=>{
 for(const hash of ['#lat=13&lat=14&lon=100','#lat=&lon=100','#lat=91&lon=100','#lat=NaN&lon=100','#lon=100'])assert.equal(readPointHash(hash),null);
 assert.throws(()=>pointHash(Infinity,100));
});
