"""Consistent bounded JSON-object parsing for metadata and source evidence."""
import json
import math
from pathlib import Path


def strict_json_loads(raw,max_bytes=20_000_000,max_depth=64):
    if not isinstance(raw,(bytes,str)):
        raise ValueError('JSON input must be UTF-8 bytes or text')
    encoded=raw if isinstance(raw,bytes) else raw.encode('utf-8')
    if len(encoded)>max_bytes:
        raise ValueError('JSON input exceeds byte limit')
    text=encoded.decode('utf-8-sig')
    depth=0;quoted=False;escaped=False
    for char in text:
        if quoted:
            if escaped:escaped=False
            elif char=='\\':escaped=True
            elif char=='"':quoted=False
        elif char=='"':quoted=True
        elif char in '[{':
            depth+=1
            if depth>max_depth:raise ValueError('JSON nesting depth exceeded')
        elif char in ']}':depth-=1
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    def finite(token):
        value=float(token)
        if not math.isfinite(value):raise ValueError('Non-finite JSON number')
        return value
    def constant(token):
        raise ValueError('Non-finite JSON constant')
    try:
        result=json.loads(text,object_pairs_hook=unique,parse_float=finite,parse_constant=constant)
    except RecursionError:
        raise ValueError('JSON nesting depth exceeded') from None
    if not isinstance(result,dict):raise ValueError('JSON object required')
    pending=[result]
    while pending:
        value=pending.pop()
        if isinstance(value,dict):
            pending.extend(value.keys());pending.extend(value.values())
        elif isinstance(value,list):pending.extend(value)
        elif isinstance(value,str):
            try:value.encode('utf-8')
            except UnicodeEncodeError:raise ValueError('Invalid Unicode surrogate in JSON string') from None
    return result


def read_json_object(path,max_bytes=64000):
    with Path(path).open('rb') as stream:
        raw=stream.read(max_bytes+1)
    return strict_json_loads(raw,max_bytes=max_bytes)
