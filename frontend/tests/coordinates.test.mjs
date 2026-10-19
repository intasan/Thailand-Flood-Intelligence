import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parseCoordinates as parse} from '../lib/coordinates.mjs';
test('coordinates and escaped Google query',()=>{
 assert.deepEqual(parse('13.75, 100.5'),{lat:13.75,lon:100.5,viewport:false});
 assert.equal(parse('https://www.google.com/maps?query=13.75%2C100.5').lon,100.5);
});
test('pin takes precedence over viewport',()=>{
 assert.deepEqual(parse('https://www.google.com/maps/place/test/@13,100,15z/data=!3d14!4d101'),{lat:14,lon:101,viewport:false});
 assert.equal(parse('https://www.google.com/maps/@13,100,15z').viewport,true);
});
test('invalid or ambiguous coordinates are rejected',()=>{
 for(const value of ['91,100','13,181','NaN,100','https://evil.example/@13,100','https://maps.app.goo.gl/test','%XX'])assert.equal(parse(value),null);
});
