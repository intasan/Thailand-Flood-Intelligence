import {seriesPlot} from '../lib/series.mjs';
export type SeriesRow={observed_at:string;value:number;unit:string;raw_sha256?:string;metadata:{timestamp_status?:string;source_quality_flag?:string;source_url?:string}};
export type ObservationSeries={station:{id:string;vertical_datum:string;metadata:{name?:string};source_url?:string};start:string;end:string;count:number;gaps:{after:string;before:string;seconds:number}[];results:SeriesRow[]};
export function thaiTime(time:string|number){return new Date(time).toLocaleString('th-TH',{timeZone:'Asia/Bangkok'});}
type PlotPoint={time:number;value:number;observed_at:string;x:number;y:number};
type Plot={segments:PlotPoint[][];points:PlotPoint[];min:number|null;max:number|null;axisMin?:number;axisMax?:number;from?:number;to?:number};
export default function StationHistory({series}:{series:ObservationSeries}){
 let plot:Plot;try{plot=seriesPlot(series.results,{start:series.start,end:series.end});}catch{return <p className="error mt-3">เวลาในข้อมูลไม่สอดคล้อง กรุณาตรวจสอบตารางก่อนใช้กราฟ</p>;}
 if(!plot.points.length)return <p className="muted mt-3">ไม่มีค่าตรวจวัดที่ใช้วาดกราฟได้</p>;
 const label=(n:number)=>n.toLocaleString('th-TH',{maximumFractionDigits:3});
 return <figure className="mt-4"><svg viewBox="0 0 320 160" className="w-full" role="img" aria-label={`ระดับน้ำสถานี ${series.station.id} ข้อมูล ${plot.points.length} ค่า เส้นขาดเมื่อไม่มีข้อมูล`}>
  <line x1="42" y1="12" x2="42" y2="130" stroke="#8ca2a9"/><line x1="42" y1="130" x2="310" y2="130" stroke="#8ca2a9"/>
  <text x="38" y="18" textAnchor="end" fontSize="10" fill="#637b84">{label(plot.axisMax!)}</text><text x="38" y="130" textAnchor="end" fontSize="10" fill="#637b84">{label(plot.axisMin!)}</text>
  {plot.segments.filter(s=>s.length>1).map((s,i)=><polyline key={i} points={s.map(p=>`${p.x},${p.y}`).join(' ')} fill="none" stroke="#087c85" strokeWidth="1.7"/>)}
  {plot.points.map(p=><circle key={p.time} cx={p.x} cy={p.y} r="1.8" fill="#087c85"><title>{thaiTime(p.time)} · {p.value} ม.</title></circle>)}
  <text x="42" y="151" fontSize="9" fill="#637b84">{new Date(plot.from!).toLocaleTimeString('th-TH',{timeZone:'Asia/Bangkok',hour:'2-digit',minute:'2-digit'})}</text><text x="310" y="151" textAnchor="end" fontSize="9" fill="#637b84">{new Date(plot.to!).toLocaleTimeString('th-TH',{timeZone:'Asia/Bangkok',hour:'2-digit',minute:'2-digit'})}</text>
 </svg><figcaption className="muted text-xs">ระดับน้ำสถานี (เมตร) · เวลาไทย UTC+7<br/>ไม่เติมค่าและไม่เชื่อมช่วงที่ขาดเกิน 15 นาทีหรือมีค่าที่ใช้ไม่ได้<br/>กราฟนี้ไม่ใช่ความลึกน้ำท่วมที่ดิน</figcaption></figure>;
}
