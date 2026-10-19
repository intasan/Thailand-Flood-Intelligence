'use client';
import {useEffect,useRef,useState} from 'react';
import * as maplibregl from 'maplibre-gl';
import {parseCoordinates} from '../lib/coordinates.mjs';
import {thaiLandArea} from '../lib/area.mjs';

type Place={id:number;name:string;admin1?:string;admin2?:string;lat:number;lon:number};
type Surface={value_m:number|null;resolution_m:number;dataset:string;limitations:string[];metadata:{fetched_at:string;attribution:string}};
type Station={id:string;value:number|null;unit:string;observed_at:string|null;freshness:string;distance_m:number;vertical_datum:string;source:string;source_url:string;lat:number;lon:number;station_metadata?:{name?:string};observation_metadata?:{data_type?:string;timestamp_status?:string}};
type Series={station:{id:string;vertical_datum:string;metadata:{name?:string}};start:string;end:string;count:number;gaps:{after:string;before:string;seconds:number}[];results:{observed_at:string;value:number;unit:string;metadata:{timestamp_status?:string}}[]};
type Assessment={risk:string;flood_depth_m:number|null;duration_hours:number|null;elevation_m:number|null;metadata:Record<string,unknown>;geometry?:GeoJSON.Polygon;area_m2?:number;perimeter_m?:number};
type Status={database:string;station_count:number|null;observation_count:number|null;validated_model_count:number};
async function get<T>(path:string):Promise<T>{const r=await fetch('/api/'+path,{cache:'no-store',signal:AbortSignal.timeout(20000)});if(!r.ok)throw Error('บริการไม่พร้อม ('+r.status+')');return r.json();}
function value(v:number|null|undefined,unit=''){return v==null?'ไม่มีข้อมูล':v.toLocaleString('th-TH',{maximumFractionDigits:2})+' '+unit;}

export default function Page(){
 const container=useRef<HTMLDivElement>(null),map=useRef<maplibregl.Map|null>(null),marker=useRef<maplibregl.Marker|null>(null);
 const stationMarkers=useRef<maplibregl.Marker[]>([]),seriesToken=useRef(0);
 const [series,setSeries]=useState<Series|null>(null),[seriesError,setSeriesError]=useState(''),[seriesBusy,setSeriesBusy]=useState(false);
 const drawing=useRef(false),vertices=useRef<number[][]>([]),serial=useRef(0);
 const [query,setQuery]=useState(''),[places,setPlaces]=useState<Place[]>([]),[searching,setSearching]=useState(false);
 const [point,setPoint]=useState<number[]|null>(null),[assessment,setAssessment]=useState<Assessment|null>(null);
 const [surface,setSurface]=useState<Surface|null>(null),[stations,setStations]=useState<Station[]>([]),[stationError,setStationError]=useState('');
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[surfaceError,setSurfaceError]=useState('');
 const [draw,setDraw]=useState(false),[vertexCount,setVertexCount]=useState(0),[mapError,setMapError]=useState(''),[status,setStatus]=useState<Status|null>(null);
 useEffect(()=>{get<Status>('v1/status').then(setStatus).catch(()=>setStatus(null));},[]);
 async function loadSeries(id:string){
  const token=++seriesToken.current;setSeries(null);setSeriesError('');setSeriesBusy(true);
  try{const data=await get<Series>('v1/observations?station_id='+encodeURIComponent(id));if(token===seriesToken.current)setSeries(data);}catch{if(token===seriesToken.current)setSeriesError('โหลดประวัติสถานีไม่ได้');}finally{if(token===seriesToken.current)setSeriesBusy(false);}
 }
 function clearStations(){stationMarkers.current.forEach(m=>m.remove());stationMarkers.current=[];seriesToken.current++;setSeries(null);setSeriesBusy(false);setSeriesError('');}
 async function assess(path:string,body:unknown){
  clearStations();
  const id=++serial.current;setBusy(true);setAssessment(null);setSurface(null);setStations([]);setError('');setSurfaceError('');setStationError('');
  const p=body as {lat?:number;lon?:number};
  const jobs:Promise<unknown>[]=[fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(20000)}).then(async r=>{if(!r.ok)throw Error('รูปแปลงหรือพิกัดไม่ถูกต้อง ('+r.status+')');const data=await r.json();if(id===serial.current)setAssessment(data);}).catch(e=>{if(id===serial.current)setError(String(e));})];
  if(p.lat!==undefined&&p.lon!==undefined){
   jobs.push(get<Surface>(`v1/elevation?lat=${p.lat}&lon=${p.lon}`).then(d=>{if(id===serial.current)setSurface(d);}).catch(()=>{if(id===serial.current)setSurfaceError('โหลดข้อมูลความสูงพื้นผิวไม่ได้ ไม่มีค่าอื่นแทน');}));
   jobs.push(get<{results:Station[]}>(`v1/stations?lat=${p.lat}&lon=${p.lon}`).then(d=>{if(id===serial.current){setStations(d.results);if(map.current)for(const station of d.results){const el=document.createElement('button');el.className='station-pin';el.style.backgroundColor=station.freshness==='recent'?'#0f766e':'#b77900';el.setAttribute('aria-label','ดูประวัติสถานี '+(station.station_metadata?.name||station.id));el.onclick=e=>{e.stopPropagation();void loadSeries(station.id);};stationMarkers.current.push(new maplibregl.Marker({element:el}).setLngLat([station.lon,station.lat]).addTo(map.current));}}}).catch(()=>{if(id===serial.current)setStationError('ฐานข้อมูลสถานีไม่พร้อม');}));
  }
  await Promise.allSettled(jobs);if(id===serial.current)setBusy(false);
 }
 function select(lon:number,lat:number){
  if(!Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180){setError('พิกัดไม่ถูกต้อง');return;}
  drawing.current=false;setDraw(false);vertices.current=[];setVertexCount(0);updateParcel();setPoint([lon,lat]);
  if(map.current){marker.current?.remove();marker.current=new maplibregl.Marker({color:'#067c86'}).setLngLat([lon,lat]).addTo(map.current);map.current.flyTo({center:[lon,lat],zoom:14});}
  void assess('v1/assess',{lat,lon});
 }
 useEffect(()=>{
  if(!container.current)return;
  try{
  const m=new maplibregl.Map({container:container.current,style:process.env.NEXT_PUBLIC_MAP_STYLE_URL||{version:8,sources:{osm:{type:'raster',tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],tileSize:256,maxzoom:19,attribution:'© OpenStreetMap contributors'}},layers:[{id:'osm',type:'raster',source:'osm'}]},center:[100.6,15.5],zoom:5,maxZoom:19});
  map.current=m;m.addControl(new maplibregl.NavigationControl(),'bottom-right');
  m.on('error',()=>setMapError('โหลดแผนที่บางส่วนไม่สำเร็จ ยังใช้พิกัดได้'));
  m.on('click',e=>{if(drawing.current){if(vertices.current.length>=999){setError('จำกัด 999 จุด');return;}vertices.current.push([e.lngLat.lng,e.lngLat.lat]);setVertexCount(vertices.current.length);updateParcel();}else select(e.lngLat.lng,e.lngLat.lat);});
  return()=>{m.remove();map.current=null;};
  }catch{map.current=null;setMapError('อุปกรณ์นี้เปิดแผนที่ไม่ได้ ยังใช้พิกัดและการค้นหาได้');}
 },[]);
 function updateParcel(){
  const m=map.current;if(!m?.isStyleLoaded())return;const v=vertices.current;
  const geometry:GeoJSON.Geometry=v.length>=3?{type:'Polygon',coordinates:[[...v,v[0]]]}:{type:'LineString',coordinates:v};
  const data:GeoJSON.FeatureCollection={type:'FeatureCollection',features:v.length>=2?[{type:'Feature',properties:{},geometry}]:[]};
  const source=m.getSource('parcel') as maplibregl.GeoJSONSource|undefined;
  if(source)source.setData(data);else{m.addSource('parcel',{type:'geojson',data});m.addLayer({id:'parcel-fill',type:'fill',source:'parcel',filter:['==','$type','Polygon'],paint:{'fill-color':'#087c85','fill-opacity':0.16}});m.addLayer({id:'parcel-line',type:'line',source:'parcel',paint:{'line-color':'#087c85','line-width':3}});}
 }
 async function search(){
  if(searching)return;
  setError('');setPlaces([]);const parsed=parseCoordinates(query);
  if(parsed){select(parsed.lon,parsed.lat);if(parsed.viewport)setError('URL นี้ระบุจุดกึ่งกลางมุมมอง กรุณาตรวจสอบหมุดหรือวางพิกัดสถานที่โดยตรง');return;}
  if(query.trim().length<2){setError('กรอกชื่อสถานที่อย่างน้อย 2 ตัวอักษร');return;}
  if(/^https?:/i.test(query)){setError('ลิงก์แบบย่อไม่ระบุพิกัด กรุณาคัดลอกพิกัดจาก Google Maps');return;}
  setSearching(true);
  try{const d=await get<{results:Place[]}>('v1/geocode?q='+encodeURIComponent(query.trim()));setPlaces(d.results);if(!d.results.length)setError('ไม่พบชื่อสถานที่ ลองชื่ออำเภอ/ชุมชน หรือเลือกพิกัดบนแผนที่');}catch{setError('บริการค้นหาไม่พร้อม ใช้ GPS คลิกแผนที่ หรือวางพิกัด lat, lon ได้');}finally{setSearching(false);}
 }
 function locate(){if(!navigator.geolocation){setError('อุปกรณ์ไม่รองรับ GPS');return;}navigator.geolocation.getCurrentPosition(p=>select(p.coords.longitude,p.coords.latitude),()=>setError('รับตำแหน่งไม่ได้ กรุณาอนุญาต GPS หรือใส่พิกัด'),{timeout:15000});}
 function finish(){if(vertices.current.length<3){setError('เลือกอย่างน้อย 3 จุด');return;}drawing.current=false;setDraw(false);setPoint(null);void assess('v1/parcels/assess',{geometry:{type:'Polygon',coordinates:[[...vertices.current,vertices.current[0]]]}});}
 function downloadParcel(){if(!assessment?.geometry)return;const a=document.createElement('a');const url=URL.createObjectURL(new Blob([JSON.stringify({type:'Feature',properties:{analysis_status:'unsupported',area_m2:assessment.area_m2,area_method:'WGS84 ellipsoidal, not cadastral survey'},geometry:assessment.geometry},null,2)],{type:'application/geo+json'}));a.href=url;a.download='my-parcel.geojson';a.click();URL.revokeObjectURL(url);}
 return <main className="shell"><aside className="sidebar">
  <p className="muted">THAILAND FLOOD INTELLIGENCE</p><h1 className="text-2xl mt-3 mb-2">รู้จักพื้นที่ของคุณ<br/>เข้าใจสถานการณ์น้ำ</h1>
  <p className="muted mb-5">ค้นหาชุมชน บ้าน สวน หรือที่ดิน แล้วตรวจสอบแหล่งข้อมูลที่ใช้ได้</p><span className="badge">ยังไม่มีผลจำลองน้ำท่วมที่รับรอง</span>
  <form className="mt-6" onSubmit={e=>{e.preventDefault();void search();}}><label htmlFor="location" className="block mb-2">ชื่อชุมชน พิกัด หรือ Google Maps URL</label><input id="location" value={query} onChange={e=>setQuery(e.target.value)} placeholder="กรุงเทพฯ หรือ 13.7563, 100.5018"/><div className="actions"><button disabled={searching} type="submit">{searching?'กำลังค้นหา…':'ค้นหาสถานที่'}</button><button type="button" onClick={locate}>⌖ ตำแหน่งของฉัน</button></div></form>
  {places.length>0&&<ul className="places mt-3" aria-label="ผลค้นหาสถานที่">{places.map(p=><li key={p.id}><button onClick={()=>{select(p.lon,p.lat);setPlaces([]);setQuery(p.name);}}><strong>{p.name}</strong><small>{[p.admin2,p.admin1].filter(Boolean).join(' · ')}</small></button></li>)}</ul>}
  <p className="muted text-xs mt-3">ค้นหาจาก GeoNames / Open-Meteo อาจไม่มีที่อยู่รายบ้าน ตรวจตำแหน่งด้วยหมุดหรือ GPS</p>
  <div className="actions"><button onClick={()=>{serial.current++;setBusy(false);marker.current?.remove();clearStations();drawing.current=true;vertices.current=[];setVertexCount(0);setDraw(true);setAssessment(null);setSurface(null);setPoint(null);setError('');updateParcel();}}>วาดขอบเขตที่ดิน</button>{draw&&<><button onClick={finish}>เสร็จสิ้น ({vertexCount})</button><button onClick={()=>{vertices.current.pop();setVertexCount(vertices.current.length);updateParcel();}}>ย้อนจุด</button><button onClick={()=>{drawing.current=false;vertices.current=[];setVertexCount(0);setDraw(false);updateParcel();}}>ยกเลิก</button></>}</div>
  {draw&&<p className="muted mt-3">คลิกอย่างน้อย 3 จุด แล้วกดเสร็จสิ้น</p>}{point&&<p className="muted mt-3">{point[1].toFixed(6)}, {point[0].toFixed(6)}</p>}
  <div role="status" aria-live="polite">{busy&&<p className="mt-4">กำลังตรวจสอบข้อมูล…</p>}{error&&<p className="error mt-4">{error}</p>}</div>
  <section className="card"><h2>ความเสี่ยงน้ำท่วมในพื้นที่</h2><p className="muted my-3">{assessment?'ยังประเมินความเสี่ยงไม่ได้':'เลือกตำแหน่งเพื่อเริ่มต้น'}</p><div className="metrics">{[['ความสูงพื้นดิน',value(assessment?.elevation_m,'ม.')],['ความลึกน้ำท่วม',value(assessment?.flood_depth_m,'ม.')],['ระยะเวลาท่วมขัง',value(assessment?.duration_hours,'ชม.')],['ระดับความเสี่ยง','ยังไม่ทราบ']].map(([title,v])=><div className="metric" key={title}><p className="muted">{title}</p><strong>{v}</strong></div>)}</div><p className="mt-4 text-sm">ไม่มีข้อมูล ≠ ปลอดภัยจากน้ำท่วม</p>{assessment?.geometry&&<><ParcelArea area={assessment.area_m2} perimeter={assessment.perimeter_m}/><p className="muted mt-3">พื้นที่ประมาณจากขอบเขตที่วาด ไม่ใช่ผลรังวัด ยังไม่มีผลน้ำท่วมครอบคลุมทั้งแปลง</p><button className="mt-3" onClick={downloadParcel}>ดาวน์โหลดขอบเขต GeoJSON</button></>}</section>
  {(surface||surfaceError)&&<section className="card"><h2>ความสูงพื้นผิวโดยประมาณ</h2><strong className="text-2xl block mt-3">{value(surface?.value_m,'ม. EGM2008')}</strong>{surface&&<><p className="muted mt-2">Copernicus GLO-90 · ความละเอียด 90 เมตร</p><p className="text-sm mt-3">อาจรวมอาคารและต้นไม้ ไม่ใช่ค่ารังวัดพื้นดินรายบ้าน และใช้สรุปน้ำท่วมโดยตรงไม่ได้</p><p className="muted text-xs mt-3">Copernicus / <a href="https://open-meteo.com/en/docs/elevation-api" target="_blank" rel="noreferrer" className="underline">Open-Meteo</a><br/>ดึงข้อมูล: {new Date(surface.metadata.fetched_at).toLocaleString('th-TH')}</p></>}{surfaceError&&<p className="error">{surfaceError}</p>}</section>}
  {point&&<section className="card"><h2>สถานีใกล้เคียงในรัศมี 20 กม.</h2>{stationError?<p className="error mt-2">{stationError}</p>:stations.length?stations.map(s=><article key={s.id} className="station"><strong>{s.station_metadata?.name||s.id} · {value(s.distance_m/1000,'กม.')}</strong><p className="muted">{s.id}</p>{s.observation_metadata?.data_type==='historical_station_observation'&&<span className="badge">ข้อมูลย้อนหลัง ไม่ใช่ข้อมูลสด</span>}<p>{value(s.value,s.unit)} · {s.freshness==='stale'?'ข้อมูลเก่า':s.freshness==='recent'?'ข้อมูลล่าสุด':'ไม่มีค่าตรวจวัด'}</p><p className="muted">datum: {s.vertical_datum}<br/>{s.observed_at?new Date(s.observed_at).toLocaleString('th-TH'):''}</p><a className="underline text-sm" href={s.source_url} target="_blank" rel="noreferrer">{s.source}</a><button className="block mt-3" onClick={()=>void loadSeries(s.id)}>ดูประวัติและช่องว่างข้อมูล</button>{s.observation_metadata?.timestamp_status?.startsWith('assumed')&&<p className="muted mt-2">เวลาใช้ timezone ที่ตั้งค่าไว้ เนื่องจากต้นฉบับไม่มี offset</p>}</article>):<p className="muted mt-2">ยังไม่มีสถานีที่นำเข้าและอนุมัติในพื้นที่นี้</p>}<p className="muted mt-3">ระดับสถานีไม่ใช่ระดับน้ำที่บ้าน</p></section>}
  {(series||seriesBusy||seriesError)&&<section className="card"><h2>ประวัติระดับน้ำในคลัง</h2>{seriesBusy&&<p className="muted mt-2">กำลังโหลด…</p>}{seriesError&&<p className="error">{seriesError}</p>}{series&&<><p className="mt-3">{series.station.metadata.name||series.station.id}</p><p className="muted">ช่วง 24 ชั่วโมงสุดท้ายที่มีในคลัง<br/>{new Date(series.start).toLocaleString('th-TH')} ถึง {new Date(series.end).toLocaleString('th-TH')}</p><p className="muted mt-2">{series.count} ค่า · ช่องว่างเกิน 15 นาที {series.gaps.length} ช่วง · ไม่เติมค่าที่หาย</p><div className="series-table mt-3"><table><thead><tr><th>เวลา</th><th>ระดับน้ำ (ม.)</th></tr></thead><tbody>{series.results.slice(-48).map(r=><tr key={r.observed_at}><td>{new Date(r.observed_at).toLocaleString('th-TH')}</td><td>{r.value}</td></tr>)}</tbody></table></div><p className="muted mt-3">แสดงท้ายสุดไม่เกิน 48 ค่า ข้อมูลเต็มอ่านได้จาก Research API<br/>datum: {series.station.vertical_datum}<br/>ข้อมูลย้อนหลังของสถานี ไม่ใช่ระดับน้ำ ณ ที่ดิน</p></>}</section>}
  <section className="card"><h2>สถานะและแหล่งข้อมูล</h2><p className="muted mt-2">ฐานข้อมูล: {status?.database==='ready'?'พร้อม':'ยังเชื่อมต่อไม่ได้'}<br/>สถานี: {value(status?.station_count)} · ค่าตรวจวัด: {value(status?.observation_count)}<br/>แบบจำลองที่ผ่านการตรวจสอบ: {value(status?.validated_model_count)}</p><a className="block mt-4 underline" href="/readiness">ตรวจความพร้อมและข้อจำกัดของระบบ ↗</a><a className="block mt-4 underline" href="/research">Research API และเอกสาร ↗</a>{assessment&&<details className="mt-4"><summary>Metadata และข้อจำกัด</summary><pre className="text-xs overflow-auto mt-2">{JSON.stringify({assessment,surface,stations},null,2)}</pre></details>}</section>
 </aside><section className="map" aria-label="แผนที่เลือกตำแหน่ง"><div ref={container} className="h-full w-full"/><div className="top"><strong>ประเทศไทย</strong><p className="muted">{draw?'กำลังวาดขอบเขต':'คลิกเลือกพื้นที่ · ยังไม่มีชั้นข้อมูลพยากรณ์น้ำท่วม'}</p>{mapError&&<p className="error text-sm">{mapError}</p>}</div></section></main>;
}

function ParcelArea({area,perimeter}:{area?:number;perimeter?:number}){
 if(area===undefined)return null;
 const units=thaiLandArea(area);
 return <div className="mt-4"><strong>{value(area,'ตร.ม.')}</strong><p className="mt-1">{units.rai} ไร่ {units.ngan} งาน {units.squareWah} ตารางวา</p><p className="muted mt-1">ความยาวขอบนอก {value(perimeter,'ม.')}</p></div>;
}
