# Hydraulic model package review — schema version 2

## Why the contract changed
Version 1 accepted self-declared review fields and hashes without loading the actual input/validation evidence. Version 2 requires evidence files and a trusted review signature. No operational v1 models were installed. V1 packages are rejected and must be independently reviewed and re-exported; there is no unsigned compatibility fallback.

This is integrity verification, not scientific validation. A signature proves possession of a trusted review key, not that flood physics, observations, survey accuracy or acceptance thresholds are correct. The operator must verify reviewer identity, competence and independence outside the software. No production reviewer/key is configured in this repository.

## Trust store (outside model storage)
Configure MODEL_REVIEWERS_FILE to an operator-owned JSON file outside MODEL_DIRECTORY. Compose mounts `data/reviewers` read-only into `/app/reviewers`, while models are separately mounted under `/app/models`. Only authorized operators should modify the trust store. Private signing keys must stay offline with the reviewer: never put them in this repository, containers, manifests, API requests or logs.

Shape of the public trust store (illustrative placeholders, not a usable key):
```json
{"reviewers":{"review-key-id":{"public_key_base64":"<base64 raw Ed25519 public key>","reviewer_id":"<verified reviewer identity>","revoked":false}}}
```
Set revoked=true to reject all packages signed by that key. Missing keys, missing trust store, unknown reviewer, revoked keys or a trust store inside model storage fail closed. The application does not generate production keys, approve packages or sign on behalf of reviewers.

## Required signed manifest
Existing hydraulic fields, validation flags and asset descriptors still apply. Add:
- schema_version: 2
- horizontal_crs: exact Rasterio CRS string, e.g. EPSG:32647
- resolution_native: two positive pixel dimensions in native CRS units. This is distinct from the stated resolution_m and must match raster metadata.
- review_key_id: enabled key identifier from the external trust store
- review_signature: base64 detached Ed25519 signature
- evidence.input_manifest: relative path and SHA256
- evidence.validation_report: relative path and SHA256

The input evidence JSON contains inputs exactly matching input_provenance. Its actual file checksum must match both the evidence descriptor and input_manifest_sha256. The validation report contains all validation fields except report_sha256, exactly matching the manifest. Its actual checksum must match both its descriptor and validation.report_sha256. Evidence paths must remain inside the model package and files must be no larger than 4 MB. Duplicate JSON keys and non-finite JSON constants are rejected.

Signature payload: remove only the top-level review_signature field, then serialize all remaining manifest fields as UTF-8 JSON with sorted keys, ensure_ascii=false, compact separators comma/colon, and allow_nan=false. Signature verification uses Ed25519 via the maintained cryptography library, not a custom cryptographic algorithm. The reviewer_id in the selected public key record must match validation.reviewed_by. Reference: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/

## Raster integrity
- Single band, known CRS, declared native resolution and vertical_datum tag matching the manifest.
- Explicit nonzero NoData so missing cells are distinguishable from valid zero-depth/dry cells.
- Every unmasked cell checked for finite, nonnegative depth/duration; duration cannot exceed the valid event interval.
- Depth and optional duration rasters must have identical CRS, transform, width and height.
- Raster asset hashes verified using streaming SHA256. Asset paths cannot escape the package.

Read-only operator audit:
```bash
cd backend
python -m app.model_audit /absolute/model-package/manifest.json
```
Exit 0 means software integrity gates passed; it does not approve a model or replace hydrologic review. Invalid packages exit 1. Public APIs report unavailable results when no trusted package covers the request. Property risk remains disabled even for integrity-checked research depth outputs.

## Operational limit
Current catalog validation re-hashes and scans raster assets. It is suitable for bounded pilot packages and low request volume, not high-throughput national serving. Production-scale serving requires an immutable, audited ingestion catalog and resource-bounded cache invalidation before publication. Browser QA and scientific pilot approval are still outstanding.
