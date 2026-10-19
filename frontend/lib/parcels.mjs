export const MAX_GEOJSON_BYTES=60000;
/** One RFC7946 WGS84 Polygon, retaining holes. Topology is checked by the API. */
export function parseParcelGeoJSON(text){
 if(new TextEncoder().encode(text).byteLength>MAX_GEOJSON_BYTES)throw new Error('ไฟล์ต้องไม่เกิน 60,000 ไบต์');
 const source=JSON.parse(text);
 if(!source||typeof source!=='object'||source.crs)throw new Error('ใช้ GeoJSON WGS84 ตาม RFC7946 โดยไม่ระบุ crs อื่น');
 let feature=source;
 if(source.type==='FeatureCollection'){
  if(!Array.isArray(source.features)||source.features.length!==1)throw new Error('เลือกไฟล์ที่มีแปลงเดียว');
  feature=source.features[0];
 }
 if(feature?.crs)throw new Error('ต้องแปลงพิกัดเป็น WGS84 ก่อนนำเข้า');
 const geometry=feature?.type==='Feature'?feature.geometry:feature;
 if(geometry?.crs||geometry?.type!=='Polygon'||!Array.isArray(geometry.coordinates)||!geometry.coordinates.length)throw new Error('รองรับ Polygon แปลงเดียว รวมรูในแปลง');
 let vertices=0;
 const coordinates=geometry.coordinates.map(ring=>{
  if(!Array.isArray(ring)||ring.length<4)throw new Error('วงแหวนต้องมีอย่างน้อย 4 จุดรวมจุดปิด');
  vertices+=ring.length;if(vertices>1000)throw new Error('ขอบเขตต้องไม่เกิน 1,000 จุดรวมรูในแปลง');
  const points=ring.map(p=>{
   if(!Array.isArray(p)||p.length!==2||!Number.isFinite(p[0])||!Number.isFinite(p[1])||Math.abs(p[0])>180||Math.abs(p[1])>90)throw new Error('ต้องใช้พิกัด 2 มิติ longitude, latitude แบบ WGS84');
   return [p[0],p[1]];
  });
  const first=points[0],last=points.at(-1);
  if(first[0]!==last[0]||first[1]!==last[1])throw new Error('วงแหวนของแปลงต้องปิด');
  return points;
 });
 return {type:'Polygon',coordinates};
}
export function parcelBounds(geometry){
 const ring=geometry.coordinates[0];
 return [[Math.min(...ring.map(p=>p[0])),Math.min(...ring.map(p=>p[1]))],[Math.max(...ring.map(p=>p[0])),Math.max(...ring.map(p=>p[1]))]];
}
