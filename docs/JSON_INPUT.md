# Strict metadata JSON inputs

Operator metadata must be an unambiguous UTF-8 JSON object. The shared `app.json_input` reader rejects duplicate object keys at every depth, including keys written with Unicode escapes that decode to the same string. It never silently chooses the first or last duplicate. NaN/Infinity constants and finite-looking exponent tokens that overflow to infinity (such as 1e400) are rejected, even in unused nested fields. A top-level array, scalar or null is not accepted as a metadata object.

A maximum of 64 nested object/array containers is allowed. The depth check respects quoted strings and escapes; braces in source URLs or evidence text do not count as nesting. Invalid UTF-8, unpaired Unicode surrogate escapes, malformed/trailing JSON and byte-limit violations reject input. Optional UTF-8 BOMs are accepted. Valid zero, negative finite numbers, false and null field values are preserved; each consuming schema still decides whether a field may contain them. No metadata field or value is repaired or rewritten.

## Coverage

| Input path | Limit / behavior |
|---|---|
| Generic local observation-import manifest | 64,000 bytes, bounded read before parsing |
| DEM/rainfall/comparison/pilot metadata | Existing per-command byte caps continue to apply |
| Network package | Existing 20 MB package cap |
| Signed model manifest/evidence/reviewer JSON | 4 MB per file; evidence hash and signature gates remain unchanged |
| Open-Meteo response/cache object | 1 MB, strict parsing before payload validation or caching |

The DEM, river-network, rainfall, exact-time level comparison and integrated pilot commands use the same parser. Signed evidence wraps parser errors in its existing `EvidenceRejected` contract. Model file hashes still refer to exact original bytes and valid canonical signature semantics are unchanged. This does not sign new evidence or certify model physics.

Provider JSON must also be strict UTF-8, rather than relying on encoding guessing. Invalid fresh responses produce explicit provider unavailability and never become cached observations/elevations. Previously cached invalid objects are evicted and fetched again under the existing quota/deadline rules; no fallback measurement is generated.

This change concerns backend metadata/source-object readers. It does not claim to replace FastAPI's public request parser or browser GeoJSON parsing. Numeric/unit/datum/time/geometry/rights checks still run separately. An unambiguous manifest is not proof of source authenticity, licence permission, scientific independence or model accuracy. No public forecast, deployment or external resource change is enabled by parsing success.
