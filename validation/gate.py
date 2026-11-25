"""Check REAL candidate evidence; missing implementations cannot produce PASS.

SPDX-License-Identifier: EPL-1.0
"""
from .compare import compare
import json
from pathlib import Path


def evaluate_cell(reference, candidate, manifest, status, expected):
    if candidate is None or manifest is None or status is None:
        return {"status":"NOT_RUN","integration_status":"INTEGRATION_PENDING", "reason":"Missing real production candidate evidence"}
    if status.get("status")!="PASS":
        return {"status":status.get("status","FAIL"),"reason":"Candidate did not complete successfully"}
    import jsonschema
    try:
        jsonschema.validate(manifest,json.loads(Path(__file__).with_name("manifest.schema.json").read_text(encoding="utf-8")))
    except jsonschema.ValidationError as error:
        return {"status":"FAIL","reason":"Incomplete/invalid R4 manifest","field":"/".join(str(x) for x in error.path)}
    for key,value in expected.items():
        if manifest.get(key)!=value:
            return {"status":"FAIL","reason":"Requested implementation identity mismatch","field":key}
    if manifest.get("backend_requested")!=manifest.get("backend_effective"):
        return {"status":"FAIL","reason":"Fallback cannot pass requested native cell"}
    for key,reference_key in (("seed","seed"),("input_hash","input_hash"),("upstream_sha","upstream_sha"),("contract_version","contract_version")):
        if manifest.get(key)!=reference[reference_key]:
            return {"status":"FAIL","reason":"Candidate manifest identity mismatch","field":key}
    return compare(reference,candidate)
