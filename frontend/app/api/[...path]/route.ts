import {NextRequest,NextResponse} from 'next/server';
export const dynamic='force-dynamic';
async function proxy(req:NextRequest,ctx:{params:Promise<{path:string[]}>}){
 const {path}=await ctx.params;
 if(path.some(p=>!/^[-a-zA-Z0-9_]+$/.test(p)))return NextResponse.json({detail:'Invalid path'},{status:400});
 const target=new URL(path.join('/'),(process.env.API_INTERNAL_URL||'http://localhost:8000')+'/');target.search=req.nextUrl.search;
 try{const body=req.method==='POST'?await req.text():undefined;if(body&&body.length>64000)return NextResponse.json({detail:'Payload too large'},{status:413});
 const res=await fetch(target,{method:req.method,body,headers:{'Content-Type':'application/json'},signal:AbortSignal.timeout(15000),cache:'no-store'});
 return new NextResponse(await res.text(),{status:res.status,headers:{'Content-Type':'application/json'}});
 }catch{return NextResponse.json({detail:'Research API unavailable'},{status:503});}
}
export const GET=proxy;export const POST=proxy;
