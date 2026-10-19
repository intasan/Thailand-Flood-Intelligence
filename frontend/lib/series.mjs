/** Visual connections only between successive valid observations; never fill missing data.
 * @param {Array<{observed_at: string, value: number | null, unit: string}>} rows
 * @param {{start?: string, end?: string, width?: number, height?: number, gapSeconds?: number}} options
 */
export function seriesPlot(rows,{start,end,width=320,height=160,gapSeconds=900}={}){
 const groups=[];let group=[],previousTime=null;const all=[];
 const close=()=>{if(group.length)groups.push(group);group=[];};
 for(const row of rows){
  const time=typeof row.observed_at==='string'&&/(Z|[+-]\d{2}:\d{2})$/.test(row.observed_at)?Date.parse(row.observed_at):NaN;
  if(!Number.isFinite(time)){close();continue;}
  if(previousTime!==null&&time<=previousTime)throw new Error('Observation timestamps must be unique and chronological');
  previousTime=time;
  if(typeof row.value!=='number'||!Number.isFinite(row.value)||row.unit!=='m'){close();continue;}
  if(group.length&&(time-group.at(-1).time)/1000>gapSeconds)close();
  const point={time,value:row.value,observed_at:row.observed_at};group.push(point);all.push(point);
 }
 close();
 if(!all.length)return {segments:[],points:[],min:null,max:null};
 const first=all[0].time,last=all.at(-1).time;
 const from=start===undefined?(first===last?first-60000:first):Date.parse(start);
 const to=end===undefined?(first===last?last+60000:last):Date.parse(end);
 if(!Number.isFinite(from)||!Number.isFinite(to)||to<=from||first<from||last>to)throw new Error('Invalid chart interval');
 const min=Math.min(...all.map(p=>p.value)),max=Math.max(...all.map(p=>p.value));
 const padding=max===min?Math.max(.1,Math.abs(min)*.01):(max-min)*.1;
 const axisMin=min-padding,axisMax=max+padding;
 const project=p=>({...p,x:42+(p.time-from)/(to-from)*(width-52),y:12+(axisMax-p.value)/(axisMax-axisMin)*(height-42)});
 return {segments:groups.map(g=>g.map(project)),points:all.map(project),min,max,axisMin,axisMax,from,to};
}
function cell(value,text=true){
 let s=value==null?'':String(value);
 if(text&&/^[\s]*[=+@-]/.test(s))s="'"+s;
 return '"'+s.replaceAll('"','""')+'"';
}
export function seriesCsv(series){
 const header=['station_id','observed_at','value','unit','vertical_datum','source_url','raw_sha256','source_quality_flag','timestamp_status'];
 const rows=series.results.map(r=>[
  cell(series.station.id),cell(r.observed_at),cell(typeof r.value==='number'&&Number.isFinite(r.value)?r.value:null,false),cell(r.unit),
  cell(series.station.vertical_datum),cell(r.metadata?.source_url||series.station.source_url),cell(r.raw_sha256),cell(r.metadata?.source_quality_flag),cell(r.metadata?.timestamp_status)
 ].join(','));
 return '\uFEFF'+[header.map(h=>cell(h)).join(','),...rows].join('\r\n');
}
