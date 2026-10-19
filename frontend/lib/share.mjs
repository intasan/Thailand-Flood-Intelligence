export function pointHash(lat,lon){
 if(!Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180)throw new RangeError('Invalid coordinate');
 return '#'+new URLSearchParams({lat:lat.toFixed(6),lon:lon.toFixed(6)}).toString();
}
export function readPointHash(hash){
 const p=new URLSearchParams(hash.replace(/^#/,''));
 if(p.getAll('lat').length!==1||p.getAll('lon').length!==1)return null;
 const a=p.get('lat'),b=p.get('lon');
 if(!a||!b||!/^[-+]?\d+(?:\.\d+)?$/.test(a)||!/^[-+]?\d+(?:\.\d+)?$/.test(b))return null;
 const lat=Number(a),lon=Number(b);
 return Number.isFinite(lat)&&Number.isFinite(lon)&&Math.abs(lat)<=90&&Math.abs(lon)<=180?{lat,lon}:null;
}
