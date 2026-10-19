"""Operator-only read-only evidence audit. Never approves or signs a package."""
import argparse,json
from .models import validate_manifest,ModelRejected

def main():
    p=argparse.ArgumentParser();p.add_argument('manifest');a=p.parse_args()
    try:
        m=validate_manifest(a.manifest)
        print(json.dumps({'status':'integrity_checks_passed','model_version':m['model_version'],'reviewed_by':m['validation']['reviewed_by'],'scientific_validity':'requires_independent_human_review'},ensure_ascii=False))
    except ModelRejected as e:
        print(json.dumps({'status':'rejected','reason':str(e)}));return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
