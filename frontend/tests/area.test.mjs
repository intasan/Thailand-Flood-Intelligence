import {test} from 'node:test';
import assert from 'node:assert/strict';
import {thaiLandArea as area} from '../lib/area.mjs';
test('Thai land units and rounding carry remain consistent',()=>{
 assert.deepEqual(area(1600),{rai:1,ngan:0,squareWah:0});
 assert.deepEqual(area(404),{rai:0,ngan:1,squareWah:1});
 assert.deepEqual(area(399.999),{rai:0,ngan:1,squareWah:0});
 assert.deepEqual(area(0),{rai:0,ngan:0,squareWah:0});
});
test('invalid area is never displayed as land measurement',()=>{
 for(const value of [-1,NaN,Infinity,'1600'])assert.throws(()=>area(value));
});
