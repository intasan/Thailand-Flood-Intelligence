import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parseParcelGeoJSON as parse,parcelBounds} from '../lib/parcels.mjs';
const polygon={type:'Polygon',coordinates:[[[100,13],[101,13],[101,14],[100,14],[100,13]],[[100.2,13.2],[100.4,13.2],[100.4,13.4],[100.2,13.2]]]};
test('Polygon and single-feature collection retain all hole rings',()=>{
 const result=parse(JSON.stringify({type:'FeatureCollection',features:[{type:'Feature',properties:{name:'TEST'},geometry:polygon}]}));
 assert.deepEqual(result,polygon);assert.deepEqual(parcelBounds(result),[[100,13],[101,14]]);
});
test('multiple parcels and projected or 3D data are not silently converted',()=>{
 assert.throws(()=>parse(JSON.stringify({type:'FeatureCollection',features:[{type:'Feature',geometry:polygon},{type:'Feature',geometry:polygon}]})));
 assert.throws(()=>parse(JSON.stringify({...polygon,crs:{type:'name',properties:{name:'EPSG:3857'}}})));
 assert.throws(()=>parse(JSON.stringify({type:'Polygon',coordinates:[[[100,13,5],[101,13,5],[101,14,5],[100,13,5]]]})));
});
test('open rings, excessive vertices and oversized UTF-8 files rejected',()=>{
 assert.throws(()=>parse(JSON.stringify({type:'Polygon',coordinates:[[[100,13],[101,13],[101,14],[100,14]]]})));
 assert.throws(()=>parse(JSON.stringify({type:'Polygon',coordinates:[Array.from({length:1001},()=>[100,13])]})));
 assert.throws(()=>parse(JSON.stringify({type:'Feature',geometry:polygon,properties:{name:'ก'.repeat(21000)}})));
});
