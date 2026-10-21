"""Model evidence integrity checks. A trusted signature does not establish hydrologic validity."""
import base64,hashlib,json,os
from pathlib import Path
from .json_input import read_json_object
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

class EvidenceRejected(ValueError):pass

def strict_json(path):
    try:return read_json_object(path,max_bytes=4_000_000)
    except ValueError as e:raise EvidenceRejected(str(e)) from e

def canonical_manifest(manifest):
    return json.dumps({k:v for k,v in manifest.items() if k!='review_signature'},sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')

def file_sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()

def local_evidence(root,descriptor,limit=4_000_000):
    path=(root/descriptor['path']).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size>limit:raise EvidenceRejected('Missing/oversized/outside evidence file')
    if file_sha256(path)!=descriptor['sha256']:raise EvidenceRejected('Evidence checksum mismatch')
    return strict_json(path)

def verify_evidence(path,manifest):
    m=manifest;root=Path(path).resolve().parent
    if m.get('schema_version')!=2:raise EvidenceRejected('Model package schema_version 2 required')
    evidence=m['evidence']
    inputs=local_evidence(root,evidence['input_manifest'])
    report=local_evidence(root,evidence['validation_report'])
    if evidence['input_manifest']['sha256']!=m['input_manifest_sha256'] or inputs['inputs']!=m['input_provenance']:raise EvidenceRejected('Input evidence does not match manifest')
    if evidence['validation_report']['sha256']!=m['validation']['report_sha256']:raise EvidenceRejected('Validation report hash not bound')
    for k in m['validation']:
        if k=='report_sha256':continue
        if report[k]!=m['validation'][k]:raise EvidenceRejected('Validation report does not match manifest')
    registry=Path(os.environ.get('MODEL_REVIEWERS_FILE','/app/reviewers/reviewers.json')).resolve()
    model_root=Path(os.environ.get('MODEL_DIRECTORY',root.parent)).resolve()
    if registry.is_relative_to(model_root):raise EvidenceRejected('Reviewer trust store must be outside model package storage')
    keys=strict_json(registry)['reviewers'];reviewer=keys[m['review_key_id']]
    if reviewer.get('revoked') is not False:raise EvidenceRejected('Reviewer key is revoked or not explicitly enabled')
    if reviewer['reviewer_id']!=m['validation']['reviewed_by']:raise EvidenceRejected('Reviewer identity mismatch')
    try:
        key=Ed25519PublicKey.from_public_bytes(base64.b64decode(reviewer['public_key_base64'],validate=True))
        key.verify(base64.b64decode(m['review_signature'],validate=True),canonical_manifest(m))
    except (ValueError,InvalidSignature) as e:raise EvidenceRejected('Model review signature invalid') from e
