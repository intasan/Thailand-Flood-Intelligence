import {NextRequest,NextResponse} from 'next/server';
import {BodyReadError,isAllowedApiRoute,readJsonBody} from '../../../lib/api-proxy.mjs';
export const dynamic='force-dynamic';
const headers={'Cache-Control':'no-store','Content-Type':'application/json'};
async function proxy(req:NextRequest,ctx:{params:Promise<{path:string[]}>}){
 const {path}=await ctx.params;
 if(!isAllowedApiRoute(req.method,path))return NextResponse.json({detail:'Unsupported API route or method'},{status:404,headers});
 try{
  const body=req.method==='POST'?await readJsonBody(req):undefined;
  const target=new URL(path.join('/'),(process.env.API_INTERNAL_URL||'http://localhost:8000')+'/');target.search=req.nextUrl.search;
  const response=await fetch(target,{method:req.method,body,headers:{'Content-Type':'application/json'},redirect:'error',signal:AbortSignal.timeout(15000),cache:'no-store'});
  return new NextResponse(await response.text(),{status:response.status,headers});
 }catch(e){
  if(e instanceof BodyReadError)return NextResponse.json({detail:e.message},{status:e.status,headers});
  return NextResponse.json({detail:'Research API unavailable'},{status:503,headers});
 }
}
export const GET=proxy;export const POST=proxy;
