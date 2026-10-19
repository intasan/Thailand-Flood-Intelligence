"""Bound POST bodies before JSON parsing or GEOS processing."""
import asyncio
from starlette.responses import JSONResponse

MAX_BODY_BYTES=64_000

class RequestBodyLimit:
    def __init__(self,app,max_bytes=MAX_BODY_BYTES):self.app,self.max_bytes=app,max_bytes

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['method']!='POST':
            return await self.app(scope,receive,send)
        async def reject(status,detail):
            await JSONResponse({'detail':detail},status_code=status,headers={'Cache-Control':'no-store'})(scope,receive,send)
        headers=dict(scope.get('headers',[]))
        try:
            declared=int(headers.get(b'content-length',b'0'))
            if declared<0:raise ValueError()
        except ValueError:return await reject(400,'Invalid Content-Length')
        if declared>self.max_bytes:return await reject(413,'Request body exceeds 64000 bytes')
        chunks=[];size=0
        async def read():
            nonlocal size
            while True:
                message=await receive()
                if message['type']=='http.disconnect':return False
                chunk=message.get('body',b'');size+=len(chunk)
                if size>self.max_bytes:raise OverflowError()
                if chunk:chunks.append(chunk)
                if not message.get('more_body',False):return True
        try:
            complete=await asyncio.wait_for(read(),timeout=10)
        except OverflowError:return await reject(413,'Request body exceeds 64000 bytes')
        except asyncio.TimeoutError:return await reject(408,'Request body timed out')
        if not complete:return
        consumed=False
        async def replay():
            nonlocal consumed
            if consumed:return {'type':'http.disconnect'}
            consumed=True
            return {'type':'http.request','body':b''.join(chunks),'more_body':False}
        await self.app(scope,replay,send)
