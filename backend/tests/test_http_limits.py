import asyncio
from app.http_limits import RequestBodyLimit

def test_chunked_oversized_body_is_not_forwarded():
    called=[];sent=[]
    async def downstream(scope,receive,send):called.append(True)
    messages=iter([{'type':'http.request','body':b'x'*40000,'more_body':True},{'type':'http.request','body':b'x'*40000,'more_body':False}])
    async def receive():return next(messages)
    async def send(m):sent.append(m)
    asyncio.run(RequestBodyLimit(downstream)({'type':'http','method':'POST','headers':[]},receive,send))
    assert not called and sent[0]['status']==413

def test_body_is_replayed_once_without_mutation():
    bodies=[]
    async def downstream(scope,receive,send):bodies.append((await receive())['body'])
    messages=iter([{'type':'http.request','body':b'{"lat":13,','more_body':True},{'type':'http.request','body':b'"lon":100}','more_body':False}])
    async def receive():return next(messages)
    async def send(m):pass
    asyncio.run(RequestBodyLimit(downstream)({'type':'http','method':'POST','headers':[]},receive,send))
    assert bodies==[b'{"lat":13,"lon":100}']
