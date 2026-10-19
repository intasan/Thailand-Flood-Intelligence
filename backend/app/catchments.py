"""Optional incremental-catchment geometry checks for the offline network audit."""
import math
from pyproj import Geod
from shapely.geometry import shape
from shapely.geometry.polygon import orient
from shapely.strtree import STRtree

GEOD = Geod(ellps='WGS84')
MAX_POSITIONS = 200000
MAX_CANDIDATE_PAIRS = 250000


def catchment_areas(reaches, provenance):
    """Return checked ellipsoidal areas, or None if no geometries were submitted.

    Planar topology in WGS84 coordinate space; antimeridian edges are rejected.
    No geometry repair, snapping, delineation or hydraulic inference is performed.
    """
    present = ['incremental_catchment_geometry' in r for r in reaches.values()]
    if not any(present):
        return None
    if not all(present):
        raise ValueError('Catchment geometries must cover every reach; partial geometry audits are not allowed')
    if not isinstance(provenance.get('catchment_evidence'), str) or not provenance['catchment_evidence'].strip():
        raise ValueError('Catchment geometry requires provenance.catchment_evidence')
    ids, polygons, areas = [], [], {}
    count = 0
    for rid, row in reaches.items():
        geometry = row['incremental_catchment_geometry']
        if not isinstance(geometry, dict) or geometry.get('type') not in ('Polygon', 'MultiPolygon') or geometry.get('crs'):
            raise ValueError(f'{rid}: require WGS84 Polygon or MultiPolygon catchment')
        parts = geometry.get('coordinates')
        if geometry['type'] == 'Polygon':
            parts = [parts]
        if not isinstance(parts, list) or not parts:
            raise ValueError(f'{rid}: empty catchment')
        for rings in parts:
            if not isinstance(rings, list) or not rings:
                raise ValueError(f'{rid}: empty catchment polygon')
            for ring in rings:
                if not isinstance(ring, list) or len(ring) < 4:
                    raise ValueError(f'{rid}: invalid catchment ring')
                count += len(ring)
                if count > MAX_POSITIONS:
                    raise ValueError('Maximum 200000 catchment coordinate positions')
                for point in ring:
                    if not isinstance(point, list) or len(point) != 2:
                        raise ValueError(f'{rid}: require 2D catchment positions')
                    try:
                        valid = all(not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v) for v in point)
                    except OverflowError:
                        valid = False
                    if not valid or not -180 <= point[0] <= 180 or not -90 < point[1] < 90:
                        raise ValueError(f'{rid}: invalid catchment coordinate')
                if ring[0] != ring[-1]:
                    raise ValueError(f'{rid}: catchment rings must be explicitly closed')
                if any(abs(a[0] - b[0]) > 180 for a, b in zip(ring, ring[1:])):
                    raise ValueError(f'{rid}: antimeridian catchments are unsupported')
        polygon = shape(geometry)
        if polygon.is_empty or not polygon.is_valid:
            raise ValueError(f'{rid}: invalid catchment topology; no automatic repair')
        if polygon.bounds[2] - polygon.bounds[0] >= 180 or polygon.bounds[3] - polygon.bounds[1] >= 90:
            raise ValueError(f'{rid}: catchment extent exceeds supported regional domain')
        components = [polygon] if polygon.geom_type == 'Polygon' else list(polygon.geoms)
        area = math.fsum(abs(GEOD.geometry_area_perimeter(orient(p, sign=1))[0]) for p in components)
        if not math.isfinite(area) or area <= 0:
            raise ValueError(f'{rid}: catchment area must be positive')
        if not polygon.covers(shape(row['geometry'])):
            raise ValueError(f'{rid}: assigned reach is not covered by its incremental catchment')
        declared = row.get('incremental_catchment_area_m2')
        if declared is not None and abs(declared - area) > max(1.0, area * .01):
            raise ValueError(f'{rid}: declared incremental area differs from geometry by more than 1% or 1 m2')
        ids.append(rid); polygons.append(polygon); areas[rid] = area
    tree = STRtree(polygons)
    candidates = 0
    for i, polygon in enumerate(polygons):
        for other in tree.query(polygon):
            j = int(other)
            if j <= i:
                continue
            candidates += 1
            if candidates > MAX_CANDIDATE_PAIRS:
                raise ValueError('Catchment overlap candidate limit exceeded; subdivide audit coverage')
            # Shared edges/points have zero area and are accepted; any areal overlap is rejected.
            if polygon.intersection(polygons[j]).area > 0:
                raise ValueError(f'Overlapping incremental catchments: {ids[i]} and {ids[j]}')
    return areas
