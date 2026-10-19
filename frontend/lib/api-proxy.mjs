export class BodyReadError extends Error {
 constructor(status,message){super(message);this.status=status;}
}
export function isAllowedApiRoute(method,path){
 if(!Array.isArray(path)||path.some(p=>typeof p!=='string'))return false;
 const joined=path.join('/');
 if(method==='POST')return ['v1/assess','v1/parcels/assess'].includes(joined);
 return (method==='GET'||method==='HEAD')&&/^(openapi\.json|health\/(live|ready)|v1\/(status|readiness|geocode|elevation|stations|observations|models\/point))$/.test(joined);
}
export async function readJsonBody(request,limit=64000,timeoutMs=10000){
 const length=request.headers.get('content-length');
 if(length!==null&&(!/^\d+$/.test(length)||!Number.isSafeInteger(Number(length))))throw new BodyReadError(400,'Invalid Content-Length');
 if(length!==null&&Number(length)>limit)throw new BodyReadError(413,'Request body too large');
 if(!/^application\/json(?:\s*;|$)/i.test(request.headers.get('content-type')||''))throw new BodyReadError(415,'Content-Type must be application/json');
 if(!request.body)return '';
 const reader=request.body.getReader();let total=0;const chunks=[];let timer;
 const timeout=new Promise((_,reject)=>{timer=setTimeout(()=>reject(new BodyReadError(408,'Request body timed out')),timeoutMs);});
 try{
  while(true){
   const next=await Promise.race([reader.read(),timeout]);
   if(next.done)break;
   total+=next.value.byteLength;
   if(total>limit)throw new BodyReadError(413,'Request body too large');
   chunks.push(next.value);
  }
  const bytes=new Uint8Array(total);let offset=0;
  for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
  try{return new TextDecoder('utf-8',{fatal:true}).decode(bytes);}catch{throw new BodyReadError(400,'Invalid UTF-8 body');}
 }catch(e){void reader.cancel().catch(()=>{});throw e;}
 finally{clearTimeout(timer);reader.releaseLock();}
}
