"""Reproduce preserved L4R1 empty-suite acceptance, then exercise repaired guards."""
from __future__ import annotations
import copy
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys
from uuid import uuid4
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import assets
import controls
import verify

def main():
    original_out=assets.OUT
    saved=original_out/'review/r1-original/controls.py'
    spec=importlib.util.spec_from_file_location('preserved_r1_controls',saved)
    old=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    output=original_out/'review'/('count-regression-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex[:8])
    before=controls.payload_hashes(assets.MODEL)
    assets.OUT=output/'empty-repro'
    old.cases=lambda:[]
    try:
        old.main()
        old_report=assets.readj(assets.OUT/'semantic-controls.json')
    finally:
        assets.OUT=original_out
    assert old_report['expected_controls']==0 and old_report['all_caught'] is True,'R1 exact empty-suite failure not reproduced'
    good=controls.cases()
    report=assets.readj(original_out/'semantic-controls.json')
    controls.require_inventory(good)
    controls.require_report(report)
    results=[]
    supplied=[('zero',[]),('nineteen',good[:-1]),('duplicate',good[:-1]+[good[0]]),('reordered',list(reversed(good)))]
    original_cases=controls.cases
    for name,planned in supplied:
        controls.cases=lambda p=planned:p
        try:
            controls.main()
        except AssertionError as exc:
            results.append({'case':name,'rejected':True,'error':str(exc)})
        else:
            raise AssertionError(name+' invalid inventory accepted')
        finally:
            controls.cases=original_cases
    for name,rows in [('zero',[]),('nineteen',report['controls'][:-1]),('duplicate',report['controls'][:-1]+[report['controls'][0]])]:
        bad=copy.deepcopy(report)
        bad['controls']=rows
        try:
            controls.require_report(bad)
        except AssertionError as exc:
            results.append({'case':'report_'+name,'rejected':True,'error':str(exc)})
        else:
            raise AssertionError(name+' invalid report accepted')
    result={'r1_empty_acceptance_reproduced':True,'repair_checks':results,
        'good_inventory_and_existing20report_accepted':True,
        'model_hashes_unchanged':before==controls.payload_hashes(assets.MODEL),
        'canonical_urdf_sha256':assets.sha(assets.MODEL/'robot_arm.urdf'),
        'current_baseline':verify.verify()}
    assert result['model_hashes_unchanged'],'regression changed canonical model'
    assets.writej(output/'report.json',result)
    assets.writej(original_out/'review/r1-count-repair.json',result)
    print(result)

if __name__=='__main__':
    main()
