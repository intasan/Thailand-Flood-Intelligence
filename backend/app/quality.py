from datetime import datetime, timezone, timedelta
import math

def validate_observation(row):
    required = ["source_id", "license_evidence", "vertical_datum", "station_id", "unit", "observed_at"]
    if any(not row.get(k) for k in required): raise ValueError("missing provenance or datum")
    if row["unit"] != "m": raise ValueError("expected metres")
    if not math.isfinite(float(row["value"])): raise ValueError("non-finite measurement")
    t=datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00"))
    if t.tzinfo is None or t > datetime.now(timezone.utc)+timedelta(minutes=5): raise ValueError("invalid timestamp")
    return row

def route_order(edges):
    """Topological order only; never a hydraulic depth calculation."""
    nodes={n for e in edges for n in e}; counts={n:0 for n in nodes}
    for a,b in edges: counts[b]+=1
    queue=sorted(n for n in nodes if counts[n]==0); result=[]
    while queue:
        n=queue.pop(0); result.append(n)
        for a,b in edges:
            if a==n:
                counts[b]-=1
                if counts[b]==0: queue.append(b)
    if len(result)!=len(nodes): raise ValueError("river graph cycle; tidal loops require dedicated treatment")
    return result
