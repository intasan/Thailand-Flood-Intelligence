/** Parse explicit coordinates only. Google @ URLs describe viewport centers, not guaranteed pins. */
export function parseCoordinates(input) {
 let text;try{text=decodeURIComponent(input.trim());}catch{return null;}
 const direct=text.match(/^(-?\d+(?:\.\d+)?)[,\s]+(-?\d+(?:\.\d+)?)$/);
 if(direct)return valid(direct[1],direct[2],false);
 let url;try{url=new URL(text);}catch{return null;}
 if(url.protocol!=='https:' || !/^(www\.)?google\.(com|co\.th)$/.test(url.hostname) || !url.pathname.startsWith('/maps'))return null;
 const pin=text.match(/!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)/);
 if(pin)return valid(pin[1],pin[2],false);
 const query=url.searchParams.get('query')||url.searchParams.get('q');
 if(query){const p=query.match(/^(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)$/);if(p)return valid(p[1],p[2],false);}
 const center=text.match(/@(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)/);
 return center?valid(center[1],center[2],true):null;
}
function valid(a,b,viewport){const lat=Number(a),lon=Number(b);return Number.isFinite(lat)&&Number.isFinite(lon)&&Math.abs(lat)<=90&&Math.abs(lon)<=180?{lat,lon,viewport}:null;}
