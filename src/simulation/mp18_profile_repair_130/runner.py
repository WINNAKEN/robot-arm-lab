"""130 prepare/run/offline consume/encode owner. Import is SDK/network/Git free."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys
import threading
import time
import types
import zipfile
from collections import namedtuple

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUT=ROOT/'outputs/mp18-profile-repair-130'
DERIVED=ROOT/'src/simulation/mp18_isaac_130'
RELEASE_SHA='c4b61d3ebbf702f1c6b5b050ad16bdf49e8042d00ad56c8abf76b3ab3c85e5e3'
FACTS={'outputs/mp18-isaac-119/native-result.json': '1898aab076128712316497d72c886fee323f715b591accd0f6027bf2dca62f9c', 'outputs/mp18-isaac-119/runs/f68441cd00534b88919cfd71f8f436a8/retrieved/process.json': '4e26c4005a16e3608f7fb699228199688f2613f53fc938abd0c04ff6055dec46', 'outputs/mp18-stage-diagnosis-124/candidate/manifest.json': 'ce52c132a270853f9ee29f06b1df851c65a80e3342656f67e50005c61ae17644', 'outputs/mp18-stage-diagnosis-124/review/source-freeze.json': '9f24b6206a679e036db4e30504d289404df08bc3e625c1e759d40580532770bc', 'outputs/mp18-stage-diagnosis-124/review/main-L4-final.json': '121d50752922d688c13da2696d550c93f128d1bf001ca379eb2d4de5730d2360', 'src/simulation/mp18_video_run_125/release.py': 'bfbef2914e44f7dc2d24b23ec477cdbdc9ad6b216e2ba1aa364862f7cc4974fa', 'src/simulation/mp18_video_run_125/runner.py': 'dbe098b33aa1dd280028211fab72e217d7672e36057365bd5416df074fc0f996', 'src/simulation/mp18_video_run_125/test_runner.py': '7785d6574a06b2d6b8a95873649e919a988fc57f092e6a3086e66fc96937a1d2', 'outputs/mp18-video-run-125/runtime-final.json': '10b743c00ef5cdd9dbf14ac044c7c14292938f1cbd92e0514ba8d0b75aa03a1c', 'outputs/mp18-video-run-125/native-result.json': 'c58efeea61812eedeecedd5ccf0ef16428ef0421e90f20285cdc73f72a77e4ea', 'outputs/mp18-layer-lifetime-126/candidate/manifest.json': '7ff93a0f9a05ad6cfe8d13d3d675127bc7526846b886fa6804c11843bd85f49a', 'outputs/mp18-layer-lifetime-126/review/source-freeze.json': '1ed21862a94341d2da27a4cde129b36a02c3a8e2429dfe62c9b27cb42b351234', 'outputs/mp18-layer-lifetime-126/review/main-L4-final.json': '57ba8312a28ebb6fdb4e6bb0b1a47f89ad8295468c6386e573012ff22e21ebed', 'outputs/mp18-layer-lifetime-126/review/main-L4-r1/publication-complete.json': '1019069c318441ea55a5063377ee29598a8c036eebefafbdf35ac67c2664059c', 'outputs/mp18-layer-lifetime-126/result.json': 'c539a79a7fbd183b757d64c1d46e28eb41f39f86fb0c34c09963c03a6f179dbd', 'outputs/mp18-video-run-125/review/source-freeze.json': '35498e4b8e19d6b38ff3a94b1c6a9b2f22aa69c076f4ac100f256e83803099a9', 'outputs/mp18-video-run-125/runs/f3bdb19d83ea4615af27ddb17150c6fc/retrieved/process.json': 'fcc1c3cdddd173d97398050beea231b022934423c7e6cc0dd545b93e9a067e3a', 'outputs/mp18-video-run-128/approval-evidence.json': '5810fff5660bbf0f4c6a3aca5af675591ce5de1747f6f883492124743816acc4', 'outputs/mp18-video-run-128/task-scope.json': '3f516148ebc5bf021af4203c8852579e2449c2574ad4868993f7927d5b7fa15b', 'src/simulation/mp18_video_run_127/release.py': 'd7dcd75333db35d36a9d77e6b3256864ff92316c9b239a6cd13b6441b2457697', 'src/simulation/mp18_video_run_127/runner.py': '122c61b21380a1b663958271ce6183754ab116b59ba4caea0d9e3356796163a1', 'src/simulation/mp18_video_run_127/test_runner.py': 'd4668b7247dda597fb7c0ca5c57ffab4590bb7eb298abb00ff28832ebdbd1eed', 'src/simulation/mp18_isaac_127/native.py': '06a36b35713337d42fdb76f6f3ac161d56d6cb3cb7ce47f4d2fa683176c22e17', 'outputs/mp18-video-run-127/review/source-freeze.json': 'dd237b11646708495fae1f2f172846a934f8bd78cc73a8f1d55dbf5302a7d5c7', 'outputs/mp18-video-run-127/review/main-L4-final.json': 'c53f5e08361890ce594416d94998a72467fb170fb173ad14423df4aabd5c2c97', 'outputs/mp18-video-run-127/runtime-final.json': 'ab575828e35f05d734f1995ef8f9dccdeaadb105714359103e766015e8ad48f7', 'outputs/mp18-video-run-127/native-result.json': '3260e173564e722b1e5cf470e7cc424ebd7d000038590a3c67d1c9ec4d1a2321', 'outputs/mp18-video-run-127/post-native-analysis/author/analysis.json': '54f531c2340e221375d1da90a1f873d6483106784fdf0d1d1b0fa765421f6e50', 'outputs/mp18-video-run-127/post-native-analysis/main/main-diagnosis.json': '18dde93eb1d570ebd6471ee1b908ff0d79f73486d10285cbfa46724cec76311b', 'outputs/mp18-video-run-127/runs/28a26406faab4d8abe1b81efc4eb80c3/retrieved/process.json': 'b8c7cc0a2eb7a52e8170dc3087a3c6b943738128a565e0af7d30e4e0e0a51df2', 'outputs/mp18-video-run-128/preparation-evidence/source-scene-settings.json': '1799229a93272b0a60eff68104d8ce152d53cae514c9fce0b1db56672f8520e9', 'outputs/mp18-layer-lifetime-126/candidate/native.py': '06a36b35713337d42fdb76f6f3ac161d56d6cb3cb7ce47f4d2fa683176c22e17', 'outputs/mp18-video-run-128/preparation-evidence/solver-order-reference.json': '7fc18350d09395a790b0df5e649167eb37654fa30851de5f16fd57579b45eef2', 'outputs/mp18-video-run-129/approval-evidence.json': '98c3139c74064b0f588c2958894ab474d8e767f883a403212f4e79baa9398530', 'outputs/mp18-video-run-128/review/source-freeze.json': 'acb4edba5085f6fa0ec6ffb9181a66f45979bc42c1b10de656933df33787d916', 'outputs/mp18-video-run-128/review/main-L4-final.json': '59f094d85d478e792afdbf3b3e3602de6c3c5f86e4de87cebc62ada5941d49b5', 'outputs/mp18-video-run-128/release-manifest.json': '5105c391e8118fff1c24d168f8d322479e68fb4075fb1d61884e8a6a30f9c94a', 'outputs/mp18-video-run-128/run-result.json': 'dde80348397ba4319acec6b2bdd0f269c9d1607e6a3d43364b2273db9bd00476', 'outputs/mp18-video-run-128/native-result.json': '4a0b99cbcb73043eefc9c25da5d7c4dadc35261607e0c062f685adc1faeec373', 'outputs/mp18-video-run-128/result-receipt.json': 'ec714b4c0b6429bd92837884efdad68ac077611d727cb10fb2b86dc81a61a931', 'outputs/mp18-video-run-128/transport.json': '8bf07b6bc203aa281c3e1f5b9d2f544e4ad629ee60cf50e9f0571ec8554b4fe4', 'outputs/mp18-video-run-128/canonical-subset-check.json': 'c58cfea68cecc6b6e9ef5a3a1876890281b1c5001709996cf672fa49f7f98058', 'outputs/mp18-video-run-128/result.json': '0a77736727baa79569cbcafe5623ed88556b2d5f5c92d416e4d8a15c7cb052a0', 'outputs/mp18-video-run-128/runtime-final.json': '3fcd00f37b35a73e5342590cfe6c1bf61ba161622195c917b100d2cfa1000376', 'outputs/mp18-video-run-128/scene-order-observation.json': '62e55ecb35736b72d8656db11af20d962b97707fc9dbbba27129da5c0bc1a896', 'src/simulation/mp18_video_run_128/release.py': 'c123e62dd43d3e8d55bafcf685f506d987ab15f49a986ff978c898e445589eb6', 'src/simulation/mp18_video_run_128/runner.py': '16c0347620189fecf0d98d2ad73a57bf5b14bf854e738a22ff9c9e3e10fff893', 'src/simulation/mp18_video_run_128/test_runner.py': '690c0ee172e2a074da315ea83272fda61d56cab4ca802541fa5826713c9c4c48', 'src/simulation/mp18_isaac_128/driver.py': 'a6cd16c1b56dce509de41048fb6c0cfa0c6d9a7bdae11fd833393b74cd257dae', 'src/simulation/mp18_isaac_128/contract.py': '9052f08394a2af45f7c73b259a9bece983393bcc0d102a82a6fb21010d5574cf', 'src/simulation/mp18_isaac_128/native.py': '2ae9e7720ee7accf8fd611ab9223fbe17d7da6dc6e827011dd3b22725e4a3e7c', 'src/simulation/mp18_isaac_128/config.json': '401d0bc27b72b628e50de1db8dba735d4e3a9ccf4ff7fd54fbb377f476415350', 'src/simulation/mp18_isaac_128/program.json': '521772bfbe4e85023bc5de67a5bc6be8ce200b0ffa5a4dbe6336161315225474', 'src/simulation/mp18_isaac_128/media.py': '08739159874ef3547ac8da3c52f3078b87215baa25e6c8e653395882368b7bba', 'outputs/isaac-physics-v1/evidence/sdk-source/lab_physx_cfg.py': '617dc7e53ad4e514dd7bcab8a46e3d30341efd86329eb9cb08f0c568f31692dc', 'outputs/isaac-physics-v1/evidence/sdk-source/lab_physx_manager.py': 'dc1a3fbabbb54a4a3f7c45bf10e25643a346b06a6d9577e8f974584df9869742', 'outputs/isaac-physics-v1/evidence/sdk-source/simulation_context.py': '4878dabac6e761437717ca037a763886c448b90d705cae3d58dcef50bb992ded', 'outputs/mp18-video-run-128/runs/d0f2b14ff76d4079a43f7ba8f218f603/retrieved/first-fault.json': 'ad813ae95f494660210de67710607f94bf6a4f8ac5b00e078d7bd4ff13029cbe', 'outputs/mp18-video-run-128/runs/d0f2b14ff76d4079a43f7ba8f218f603/retrieved/report.json': '10b5bf9b07e0fd015e50be96d309293d6a4dea2a2c9645384afc05d3e140631e', 'outputs/mp18-video-run-128/runs/d0f2b14ff76d4079a43f7ba8f218f603/retrieved/process.json': '068d88f9f5722b694c838a88d7a546ecd71c5ddb7fd1c9b3f4293670a4bdc150', 'outputs/mp18-video-run-128/runs/d0f2b14ff76d4079a43f7ba8f218f603/retrieved/recovery-seal.json': '3e03b55eb23c962bfe5f36d416107c0e68305f14670cf9abd958f992dd294ca8', 'outputs/mp18-video-run-128/runs/d0f2b14ff76d4079a43f7ba8f218f603/retrieved/fresh-stage.json': '60cb5748a8a13a19ae3876f6546c68468b2ef7b1ec30fe2f5beb5443a2762533', 'outputs/mp18-video-run-128/runs/d0f2b14ff76d4079a43f7ba8f218f603/retrieved/runtime-inertias.json': '759f5c4aa11f37e49c54d893c3024a85cacf9f5ab3022b06eab705dc72ba1c84', 'outputs/mp18-video-run-128/runs/d0f2b14ff76d4079a43f7ba8f218f603/retrieved/import-settings.json': '30021a782551813e238d797f8b91ec7426c4acfd2b1d2c61d1fba523e3042548', 'outputs/mp18-video-run-128/runs/d0f2b14ff76d4079a43f7ba8f218f603/retrieved/sdk.json': '8f9cb3952dbe7e3499b50193af2583ef4ea7917e1ef706e6996bc36cca62fea8', 'outputs/mp18-profile-repair-130/source-authorization.json': '84dc2af53bdc0583fea11894587759d3f060c53c8b6977e6424833baf4748e86', 'outputs/mp18-video-run-129/review/source-freeze.json': '703a61e5677d3fc314dcd866dc93017ef1050c19366be677906025ad66735ebc', 'outputs/mp18-video-run-129/review/main-L4-final.json': '470417f31e9832ee1a083f4e13bc17e88bc199158b00b7964e2c548c1419a317', 'outputs/mp18-video-run-129/release-manifest.json': '913f404d748130e9048b6d505a56cb40327a28b0568e8ce56cadd10f33e90970', 'outputs/mp18-video-run-129/run-result.json': '129a19ca07d134b12259ce228ee6268315701042559009d38889f715e29e2c8e', 'outputs/mp18-video-run-129/native-result.json': 'b4a5da8875e8a801a330f49f1ba41ac748c9cfdad5b3e802df95631904519978', 'outputs/mp18-video-run-129/result-receipt.json': 'a4eedf1b98a1bfb84e39bf9480f5f9d858611c6bf2a77300af0ded3f4653da83', 'outputs/mp18-video-run-129/transport.json': '3602dfceb3e49d4717a316f58e5b24a52171d49c7b17c0f10fcca85305af1a30', 'outputs/mp18-video-run-129/canonical-subset-check.json': '14531b4d531d51c0af177b35f07e008ffa89272bf370f88cb9a1ba9d26cc9572', 'outputs/mp18-video-run-129/post-native-analysis/author/analysis-and-proposal.json': '7cb5f22715a7f01f70d85b642f33fdb0e6ee2a6b7831a500027ab79766376731', 'outputs/mp18-video-run-129/post-native-analysis/main/main-diagnosis.json': '5f36f28156d2fd5169eb3d92b516ddc2d71e1c2cb91017a0ba0787b5a86de585', 'outputs/mp18-video-run-129/post-native-analysis/main/publication-complete.json': '15e5536023b992f6b4507ed2a7d40627ccbc47943fc9b5095e63e2a31787a023', 'src/simulation/mp18_video_run_129/release.py': '9e14feadc9ae8c87d9ca97e5c4805dee311474dd8e2a8bf2f5c68202206152ec', 'src/simulation/mp18_video_run_129/runner.py': '5cc4b44ed962977580eb17a84c20fd483b51c2e0bcee01eca597acc569427789', 'src/simulation/mp18_video_run_129/test_runner.py': '9022c3cb93d632291cfdc21308599efcfa342da49ef35f5bbaea637d1f81ca38', 'src/simulation/mp18_isaac_129/driver.py': 'd7cf60fbc1b1f9b3095c99ce17bd7dbbb60f19fc7094efe26dcf9aabf359898d', 'src/simulation/mp18_isaac_129/contract.py': '9052f08394a2af45f7c73b259a9bece983393bcc0d102a82a6fb21010d5574cf', 'src/simulation/mp18_isaac_129/native.py': 'e78af630c5dfda106dca14d3059065c0e060c63671e2ba8b3d0756cd86b1dcd8', 'src/simulation/mp18_isaac_129/config.json': '401d0bc27b72b628e50de1db8dba735d4e3a9ccf4ff7fd54fbb377f476415350', 'src/simulation/mp18_isaac_129/program.json': '521772bfbe4e85023bc5de67a5bc6be8ce200b0ffa5a4dbe6336161315225474', 'src/simulation/mp18_isaac_129/media.py': '25800f7e643da6bf0b14fc11ad514db6be55a9f25b3b32026e5b3d845e2b1c84', 'outputs/mp18-video-run-129/runs/c72365f5de08447fbce38165f7c8dbff/retrieved/first-fault.json': 'e903e2f2a95d6451b8bf9ef468c0618c42dc70261d98f17ecd3ecb868bc7b692', 'outputs/mp18-video-run-129/runs/c72365f5de08447fbce38165f7c8dbff/retrieved/report.json': '24c3d60c95c70b810b9ce8859f62d3df76dc934ebcb48486344f52b7edfc218d', 'outputs/mp18-video-run-129/runs/c72365f5de08447fbce38165f7c8dbff/retrieved/process.json': '9a28994109f3d458675cc6c59c049496c60385762c9df5b30d2cdb20f0efb919', 'outputs/mp18-video-run-129/runs/c72365f5de08447fbce38165f7c8dbff/retrieved/recovery-seal.json': 'ca6b2859a2e5b99b6a5be216b5c2726c64bda22bef4d7e603f186b31fddbf46c', 'outputs/mp18-video-run-129/runs/c72365f5de08447fbce38165f7c8dbff/retrieved/fresh-stage.json': '3681b325e55339e49fa540f407dac5cf80c348be79dfa01cdf4e76d6840ae19a', 'outputs/mp18-video-run-129/runs/c72365f5de08447fbce38165f7c8dbff/retrieved/runtime-inertias.json': '759f5c4aa11f37e49c54d893c3024a85cacf9f5ab3022b06eab705dc72ba1c84', 'outputs/mp18-video-run-129/runs/c72365f5de08447fbce38165f7c8dbff/retrieved/import-settings.json': 'c739f66d45333378d3874d51a589c425c0ae4c67f54a09bd092fdbc6f4770439', 'outputs/mp18-video-run-129/runs/c72365f5de08447fbce38165f7c8dbff/retrieved/sdk.json': '6faee8904841379ca93d717adfbd00811908001d494f0d4f47d259531cb013ab', 'outputs/mp18-video-run-129/runs/c72365f5de08447fbce38165f7c8dbff/retrieved/constraint-order.json': '94b8c571ab5d9d20e115987a9b39745e55f0983450d40dae3cae3452c6da61d8'}

IDENTITY=('nonce','run_id','driver_sha256','bundle_sha256','bundle_bytes','job_sha256')


def _load_release():
    p=HERE/'release.py';value=p.read_bytes()
    if hashlib.sha256(value).hexdigest()!=RELEASE_SHA:raise ValueError('Release helper pin before execution')
    module=types.ModuleType('release130_checked');module.__file__=str(p);sys.modules[module.__name__]=module
    exec(compile(value,str(p),'exec'),module.__dict__)
    return module


R=_load_release()
need,parse,encode,digest=R.need,R.parse,R.encode,R.digest
Grant=namedtuple('Grant','raw reply_raw source_sha prepared_sha start end nonce permission_raw')
Snapshot=namedtuple('Snapshot','files inputs generated manifest_raw source_sha out prepared_raw bundle job_raw record_raw grant')


def _unique(rows):return tuple(sorted(dict(rows).items()))


def current(snapshot):
    R.verify_files(snapshot.files)
    if snapshot.grant is not None:
        need(R.read(snapshot.out/'user-budget-grant.json')==snapshot.grant.raw and
             R.read(snapshot.out/'user-budget-reply.json')==snapshot.grant.reply_raw and
             R.read(snapshot.out/'new-runtime-permission.json')==snapshot.grant.permission_raw,'Current actual130 grant/reply bytes')


def generated_bytes(snapshot,name):
    value=dict(snapshot.generated)[name];pin=parse(snapshot.manifest_raw)['files'][name]
    need(digest(value)==pin['sha256'] and len(value)==pin['bytes'],'Captured generated source pin')
    return value


def driver(snapshot):
    current(snapshot)
    data=generated_bytes(snapshot,'driver.py')
    D=R.load_raw('derived_driver130_'+str(id(snapshot)),data,DERIVED/'driver.py')
    D.OUT=snapshot.out
    bind_driver(D,snapshot,lambda:current(snapshot))
    return D


def bind_driver(D,snapshot,guard):
    inputs=dict(snapshot.inputs)
    def resolver(path):
        R.path_guard(path)
        value=inputs.get(str(path));need(type(value) is bytes,'Closed immutable payload input')
        return value
    D.bind_local_authority(guard,resolver)


CONTINUATION_FILES=('outputs/mp18-profile-repair-130/source-authorization.json','outputs/mp18-video-run-128/approval-evidence.json','outputs/mp18-video-run-128/task-scope.json')


def _continuation_records(facts):
    localraw,authorityraw,taskraw=[facts[p] for p in CONTINUATION_FILES]
    need(all(digest(facts[p])==FACTS[p] for p in CONTINUATION_FILES),'Captured local-only reference/request/spent-allocation SHA')
    local,authority,task=map(parse,(localraw,authorityraw,taskraw))
    keys={'unit','kind','actual_authority_unit','actual_authority_path','actual_authority_sha256','exhausted_runtime_allocation_path','exhausted_runtime_allocation_sha256','reply_text','authorized_local_actions','does_not_grant_runtime_permission','requires_new_explicit_user_permission_before_SDK','new_user_reply_fabricated','hardware_approved'}
    need(type(local) is dict and set(local)==keys and type(local['unit']) is int and local['unit']==130 and local['kind']=='LOCAL_REPAIR_ONLY_REFERENCE_TO_EXISTING_USER_REQUEST','Closed130 local-only source authorization')
    need(type(local['actual_authority_unit']) is int and local['actual_authority_unit']==128 and local['actual_authority_path']==CONTINUATION_FILES[1] and local['actual_authority_sha256']==digest(authorityraw) and local['exhausted_runtime_allocation_path']==CONTINUATION_FILES[2] and local['exhausted_runtime_allocation_sha256']==digest(taskraw),'Same captured original128 request and spent allocation')
    need(type(authority) is dict and set(authority)=={'unit','kind','reply_text','source','authorized_goal','hardware_approved'} and type(authority['unit']) is int and authority['unit']==128 and authority['kind']=='ACTUAL_CURRENT_USER_REQUEST' and authority['source']=='current_user_message_in_this_conversation','Original actual128 user request retained')
    need(local['reply_text']==authority['reply_text'] and type(local['reply_text']) is str and len(local['reply_text'])>0 and local['authorized_local_actions']==['source_repair','HOST','independent_review','local_prepare'] and local['does_not_grant_runtime_permission'] is True and local['requires_new_explicit_user_permission_before_SDK'] is True and local['new_user_reply_fabricated'] is False and local['hardware_approved'] is False and authority['hardware_approved'] is False,'Local work only; no additional runtime allowance')
    taskkeys={'allowed_runtime_units','criteria_changes_allowed','fixed_remote_period_s_per_unit','hardware_approved','kind','max_SDK_per_unit','max_sum_remote_periods_s','max_total_SDK','new_user_reply_fabricated','physical_CAN','physical_RS485','request_sha256','retry_per_unit','task_id'}
    need(type(task) is dict and set(task)==taskkeys and task['kind']=='ROOT_BOUND_GOAL_ALLOCATION' and task['task_id']=='j6-fix-large-motion-20261107-128','Closed original exhausted goal allocation')
    need(type(task['allowed_runtime_units']) is list and all(type(x) is int for x in task['allowed_runtime_units']) and task['allowed_runtime_units']==[128,129] and 130 not in task['allowed_runtime_units'],'Original allocation excludes130')
    for key,value in {'fixed_remote_period_s_per_unit':2700,'max_SDK_per_unit':1,'max_sum_remote_periods_s':5400,'max_total_SDK':2,'retry_per_unit':0}.items():
        need(type(task[key]) is int and task[key]==value,'Original exhausted allocation remains unchanged')
    need(task['request_sha256']==digest(authorityraw) and task['criteria_changes_allowed'] is False and task['hardware_approved'] is False and task['new_user_reply_fabricated'] is False and task['physical_CAN']=='NOT_RUN' and task['physical_RS485']=='NOT_RUN','Original goal remains hardwarefalse/criteria unchanged')
    return authority



def _prior128_records(facts):
    prefix='outputs/mp18-video-run-128/'
    fraw=facts[prefix+'review/source-freeze.json'];f=parse(fraw);l=parse(facts[prefix+'review/main-L4-final.json'])
    need(f['unit']==128 and l['unit']==128 and l['phase']=='L4' and type(l['round']) is int and l['round'] in (1,2) and l['non_author'] is True and l['verdict']=='PASS' and l['unmet']==0 and l['unresolved_count']==0 and l['source_freeze_sha256']==digest(fraw),'Current reviewed128 immutable F2/history')
    for p in ('release.py','runner.py','test_runner.py'):
        rel='src/simulation/mp18_video_run_128/'+p;need(f['files'][rel]['sha256']==digest(facts[rel]) and f['files'][rel]['bytes']==len(facts[rel]),'Original128 source author bytes')
    for p in ('driver.py','contract.py','native.py','config.json','program.json','media.py'):
        rel='src/simulation/mp18_isaac_128/'+p;need(f['files'][rel]['sha256']==digest(facts[rel]) and f['files'][rel]['bytes']==len(facts[rel]),'Original128 generated bytes')
    run,native,receipt,transport,check=[parse(facts[prefix+n]) for n in ('run-result.json','native-result.json','result-receipt.json','transport.json','canonical-subset-check.json')]
    rid='d0f2b14ff76d4079a43f7ba8f218f603'
    need(run['unit']==128 and run['run_id']==rid and run['status']=='FAIL' and run['native_consumer_exit']==2 and run['actual_prior_SDK']==3 and run['new_SDK_max']==1 and run['retry']==0,'128 actual fourth SDK consumed as failure')
    need(native['unit']==119 and native['run_id']==rid and native['SDK_reaped'] is True and native['status']=='FAIL' and {p['name']:p['status'] for p in native['phases']}=={'import':'PASS','hold':'PASS','small':'FAIL','large':'NOT_RUN'},'128 sourcePASS is not nativePASS')
    need(receipt['unit']==128 and receipt['run_id']==rid and receipt['native_consumer_exit']==2 and transport['child_state']=='REAPED' and transport['job_active_after']==0 and transport['raw_complete'] is True and transport['actual_child_exit_code']==0,'Completed canonical128 transport/consumer')
    need(check['unit']==128 and check['kind']=='SEALED_SUBSET_MATCHES_COMPLETED_CANONICAL_CONSUMER' and check['files']==8 and check['mismatches']==[],'Canonical128 sealed subset identity')
    process=parse(facts[prefix+'runs/'+rid+'/retrieved/process.json'])
    need(process['child_pid']==39812 and process['child_state']=='REAPED' and process['job_active_after']==0 and process['raw_complete'] is True and process['run_id']==rid,'Actual128 raw process reaped; uint64 retained by Python integer')



def _prior129_records(facts):
    prefix='outputs/mp18-video-run-129/';rid='c72365f5de08447fbce38165f7c8dbff'
    fraw=facts[prefix+'review/source-freeze.json'];l=parse(facts[prefix+'review/main-L4-final.json']);f=parse(fraw)
    need(f['unit']==129 and l['unit']==129 and l['phase']=='L4' and l['non_author'] is True and l['verdict']=='PASS' and l['unmet']==0 and l['unresolved_count']==0 and l['source_freeze_sha256']==digest(fraw),'Reviewed129 source history retained')
    for group,names in (('mp18_video_run_129',('release.py','runner.py','test_runner.py')),('mp18_isaac_129',('driver.py','contract.py','native.py','config.json','program.json','media.py'))):
        for n in names:
            path='src/simulation/'+group+'/'+n;need(f['files'][path]['sha256']==digest(facts[path]) and f['files'][path]['bytes']==len(facts[path]),'Current immutable129 original bytes')
    run,native,receipt,transport,check=[parse(facts[prefix+n]) for n in ('run-result.json','native-result.json','result-receipt.json','transport.json','canonical-subset-check.json')]
    need(run['unit']==129 and run['run_id']==rid and run['actual_prior_SDK']==4 and run['new_SDK_max']==1 and run['retry']==0 and run['status']=='FAIL' and run['native_consumer_exit']==2,'Actual fifth SDK129 consumed and failed')
    need(native['unit']==119 and native['run_id']==rid and native['status']=='FAIL' and native['SDK_reaped'] is True and {p['name']:p['status'] for p in native['phases']}=={'import':'PASS','hold':'PASS','small':'FAIL','large':'NOT_RUN'},'129 native J6 failure is not large acceptance')
    need(receipt['unit']==129 and receipt['run_id']==rid and receipt['archive_bytes']==157230506 and receipt['archive_sha256']=='266b8537ef49a9b510a43d45092d9ec6e68b9284d237aff4e98c3823c581a06d' and receipt['native_consumer_exit']==2 and transport['child_state']=='REAPED' and transport['job_active_after']==0 and transport['raw_complete'] is True and transport['actual_child_exit_code']==0,'Completed canonical129 archive and reaped transport')
    need(check['unit']==129 and check['kind']=='SEALED_SUBSET_MATCHES_COMPLETED_CANONICAL_CONSUMER' and check['files']==9 and check['mismatches']==[],'Canonical129 nine-file sealed identity')
    process=parse(facts[prefix+'runs/'+rid+'/retrieved/process.json'])
    need(process['child_pid']==50560 and process['child_state']=='REAPED' and process['raw_complete'] is True and process['job_active_after']==0 and process['run_id']==rid,'Exact raw129 process consumed, large birth integer preserved')



def runtime_permission(out=OUT):
    # Missing permission is rejected before budget/helper reads or any admission mutation.
    raw=R.read(out/'new-runtime-permission.json')
    need(len(raw)<=65536,'Bounded new explicit runtime permission')
    e=parse(raw)
    keys={'unit','kind','approved','reply_text','conversation_ref','source_freeze_sha256','L4_report_sha256','original_request_sha256','exhausted_allocation_sha256','additional_SDK_max','retry','duration_s','hardware_approved'}
    need(type(e) is dict and set(e)==keys and type(e['unit']) is int and e['unit']==130 and e['kind']=='NEW_EXPLICIT_RUNTIME_PERMISSION' and e['approved'] is True and e['hardware_approved'] is False,'Closed actual new130 runtime permission')
    for key,value in {'additional_SDK_max':1,'retry':0,'duration_s':2700}.items():
        need(type(e[key]) is int and e[key]==value,'New permission maxSDK1/no retry/fixed2700')
    need(all(type(e[k]) is str and 0<len(e[k].strip())<=16000 for k in ('reply_text','conversation_ref')) and 'permission_sha256=' not in e['conversation_ref'],'Actual new reply/context without embedded permission token')
    facts={p:R.read(ROOT/p) for p in CONTINUATION_FILES}
    authority=_continuation_records(facts)
    need(e['reply_text']!=authority['reply_text'],'Original goal-only quote is not a fresh runtime permission')
    for key in ('source_freeze_sha256','L4_report_sha256','original_request_sha256','exhausted_allocation_sha256'):
        need(type(e[key]) is str and re.fullmatch('[0-9a-f]{64}',e[key]),'Closed new permission SHA')
    need(e['original_request_sha256']==digest(facts[CONTINUATION_FILES[1]]) and e['exhausted_allocation_sha256']==digest(facts[CONTINUATION_FILES[2]]),'New permission refers to original request and exhausted allocation without rearming')
    fraw=R.read(out/'review/source-freeze.json');lraw=R.read(out/'review/main-L4-final.json');f,l=parse(fraw),parse(lraw)
    need(type(f.get('unit')) is int and f['unit']==130 and e['source_freeze_sha256']==digest(fraw),'Permission bound to current final130 F')
    need(type(l.get('unit')) is int and l['unit']==130 and l.get('phase')=='L4' and type(l.get('round')) is int and l['round'] in (1,2) and l.get('non_author') is True and l.get('verdict')=='PASS' and type(l.get('unmet')) is int and l['unmet']==0 and type(l.get('unresolved_count')) is int and l['unresolved_count']==0 and l.get('source_freeze_sha256')==digest(fraw) and e['L4_report_sha256']==digest(lraw),'Permission bound to actual current typed final mainL4')
    return raw,e



def source_snapshot(out=OUT):
    source_sha,rows=R.review_capture(out)
    generated,manifest,release_rows=R.verify_release()
    rows.extend(release_rows)
    facts={}
    for rel,expected in FACTS.items():
        p=ROOT/rel;value=R.read(p);need(digest(value)==expected,'PriorSDK/candidate/latestapproval immutable evidence')
        rows.append((str(p),value));facts[rel]=value
    _continuation_records(facts)
    _prior128_records(facts)
    _prior129_records(facts)
    prior=parse(facts['outputs/mp18-isaac-119/native-result.json'])
    need(prior['unit']==119 and prior['run_id']=='f68441cd00534b88919cfd71f8f436a8' and prior['status']=='FAIL' and
         prior['SDK_reaped'] is True and prior['remote_attempts']==1,'Original first actual SDK failure retained')
    oldrun=parse(facts['outputs/mp18-video-run-125/runtime-final.json'])
    oldnative=parse(facts['outputs/mp18-video-run-125/native-result.json'])
    oldprocess=parse(facts['outputs/mp18-video-run-125/runs/f3bdb19d83ea4615af27ddb17150c6fc/retrieved/process.json'])
    oldid='f3bdb19d83ea4615af27ddb17150c6fc'
    need(oldrun['unit']==125 and oldrun['run_id']==oldid and oldrun['status']=='IMPORT_FAILED' and
         oldrun['actual_new_SDK']==1 and oldrun['actual_prior_SDK']==1 and oldrun['total_actual_SDK']==2 and
         oldrun['SDK_reaped'] is True and oldrun['frames']==0 and oldrun['completed_steps']==0 and
         oldrun['phases']=={'import':'FAIL','hold':'NOT_RUN','small':'NOT_RUN','large':'NOT_RUN'},'Original125 SDK2 history is consumed FAIL')
    need(oldnative['unit']==119 and oldnative['run_id']==oldid and oldnative['status']=='FAIL' and
         oldnative['SDK_reaped'] is True and oldnative['remote_attempts']==1 and
         {p['name']:p['status'] for p in oldnative['phases']}==oldrun['phases'] and
         oldprocess['run_id']==oldid and oldprocess['child_pid']==38180 and oldprocess['raw_complete'] is True and
         oldprocess['terminal'] is True and oldprocess['child_state']=='REAPED' and oldprocess['job_active_after']==0 and
         oldprocess['actual_child_exit_code']==1,'Actual125 SDK reaped failure, never upgraded')
    fraw=facts['outputs/mp18-layer-lifetime-126/review/source-freeze.json'];f126=parse(fraw)
    lraw=facts['outputs/mp18-layer-lifetime-126/review/main-L4-final.json'];l126=parse(lraw)
    praw=facts['outputs/mp18-layer-lifetime-126/review/main-L4-r1/publication-complete.json'];pub126=parse(praw)
    result126=parse(facts['outputs/mp18-layer-lifetime-126/result.json'])
    candidate126=parse(facts['outputs/mp18-layer-lifetime-126/candidate/manifest.json'])
    need(type(f126['unit']) is int and f126['unit']==126 and type(f126['files']) is list and len(f126['files'])==16 and
         f126['native_acceptance']=='NOT_RUN' and f126['SDK']==0 and f126['SSH']==0,'126 local-only source freeze')
    need(l126['unit']==126 and l126['phase']=='L4' and type(l126['round']) is int and l126['round'] in (1,2) and
         l126['non_author'] is True and l126['verdict']=='PASS' and l126['unmet']==0 and l126['unresolved_count']==0 and
         l126['source_freeze_sha256']==digest(fraw),'Current126 final local source authority')
    need(pub126['unit']==126 and pub126['phase']=='L4' and pub126['kind']=='FINAL_PUBLICATION_INTEGRITY' and
         pub126['verdict']=='PASS' and pub126['unmet']==0 and pub126['unresolved_count']==0 and pub126['hash_byte_mismatches']==0 and
         pub126['source_freeze_sha256']==digest(fraw) and pub126['report_sha256']==digest(lraw),'Current126 publication binds exact report/F')
    need(result126['unit']==126 and result126['status']=='SOURCE_LOCAL_CANDIDATE_PASS' and
         result126['actual_runtime_acceptance']=='NOT_RUN' and result126['source_freeze_sha256']==digest(fraw) and
         result126['mismatches']==0 and result126['new_SDK']==0 and result126['new_SSH']==0 and
         result126['L4']['sha256']==digest(lraw) and result126['L4']['publication_sha256']==digest(praw) and
         result126['original_125_failure_preserved'] is True and result126['original_125_SDK1_consumed'] is True,
         '126 code acceptance cannot become native or reopen125')
    need(candidate126['unit']==126 and candidate126['kind']=='LOCAL_UNDEPLOYED_NATIVE_CANDIDATE' and
         candidate126['approved_to_execute'] is False and candidate126['SDK_initializations']==0 and candidate126['SSH_launches']==0 and
         candidate126['native_sha256']==R.CANDIDATE_SHA==result126['native']['sha256']==digest(facts[R.CANDIDATE]) and
         candidate126['bytes']==result126['native']['bytes']==len(facts[R.CANDIDATE])==51296 and
         candidate126['outside_function_bytes_unchanged'] is True,'Exact126 candidate in fresh130 payload')
    need(len({p['path'].casefold() for p in f126['files']})==16,'Unique126 source pin inventory')
    for pin in f126['files']:
        p=ROOT/pin['path'];value=R.read(p)
        need(digest(value)==pin['sha256'] and len(value)==pin['bytes'],'Current126 original source pin')
        rows.append((str(p),value))
    need(manifest['native_exact129'] is True and manifest['native_base_sha256']==R.NATIVE_BASE_SHA and
         digest(generated['native.py'])==manifest['files']['native.py']['sha256'], 'Current generated130 native differs from historical126 base identity')
    runtime127=parse(facts['outputs/mp18-video-run-127/runtime-final.json'])
    native127=parse(facts['outputs/mp18-video-run-127/native-result.json'])
    process127=parse(facts['outputs/mp18-video-run-127/runs/28a26406faab4d8abe1b81efc4eb80c3/retrieved/process.json'])
    id127='28a26406faab4d8abe1b81efc4eb80c3'
    phases127={'import':'PASS','hold':'PASS','small':'FAIL','large':'NOT_RUN'}
    need(runtime127['unit']==127 and runtime127['run_id']==id127 and runtime127['actual_prior_v4_SDK']==2 and
         runtime127['actual_new_SDK']==1 and runtime127['SDK_pid']==52020 and runtime127['SDK_reaped'] is True and
         runtime127['frames']==120 and runtime127['completed_steps']==1429 and
         runtime127['initialization_fixed_verified'] is True and {p['name']:p['status'] for p in runtime127['phases']}==phases127,
         'Original127 third actualSDK smallFAIL preserved')
    need(native127['unit']==119 and native127['run_id']==id127 and native127['status']=='FAIL' and native127['SDK_reaped'] is True and
         {p['name']:p['status'] for p in native127['phases']}==phases127 and process127['run_id']==id127 and
         process127['child_pid']==52020 and process127['child_state']=='REAPED' and process127['raw_complete'] is True and
         process127['job_active_after']==0,'127 nativeFAIL is current reaped history, not successful large motion')
    taskraw=facts['outputs/mp18-video-run-128/task-scope.json'];task=parse(taskraw)
    taskkeys={'allowed_runtime_units','criteria_changes_allowed','fixed_remote_period_s_per_unit','hardware_approved','kind',
        'max_SDK_per_unit','max_sum_remote_periods_s','max_total_SDK','new_user_reply_fabricated','physical_CAN','physical_RS485',
        'request_sha256','retry_per_unit','task_id'}
    need(type(task) is dict and set(task)==taskkeys and task['kind']=='ROOT_BOUND_GOAL_ALLOCATION' and
         task['task_id']=='j6-fix-large-motion-20261107-128','Closed immutable goal allocation')
    need(type(task['allowed_runtime_units']) is list and all(type(x) is int for x in task['allowed_runtime_units']) and
         task['allowed_runtime_units']==[128,129] and 130 not in task['allowed_runtime_units'],'Current130 is one of exactly130/130')
    for key,value in {'fixed_remote_period_s_per_unit':2700,'max_SDK_per_unit':1,'max_sum_remote_periods_s':5400,'max_total_SDK':2,'retry_per_unit':0}.items():
        need(type(task[key]) is int and task[key]==value,'Exact goal allocation quota/period')
    need(task['criteria_changes_allowed'] is False and task['hardware_approved'] is False and task['new_user_reply_fabricated'] is False and
         task['physical_CAN']=='NOT_RUN' and task['physical_RS485']=='NOT_RUN' and
         task['request_sha256']==digest(facts['outputs/mp18-video-run-128/approval-evidence.json']), 'Actual unchanged criteria/request hardwarefalse allocation')

    cfg=parse(generated['config.json']);inputs={str(DERIVED/n):b for n,b in generated.items()}
    for name,pin in cfg['model_pins'].items():
        p=ROOT/cfg['model_dir']/name;b=R.read(p)
        need(digest(b)==pin['sha256'] and len(b)==pin['bytes'],'Current original model bytes')
        rows.append((str(p),b));inputs[str(p)]=b
    for name,item in cfg['refs'].items():
        p=ROOT/item['path'];b=R.read(p);need(digest(b)==item['sha256'],'Current installed-reference input bytes')
        rows.append((str(p),b));inputs[str(p)]=b
    cap=R.read(ROOT/R.CAP);need(digest(cap)==R.CAP_SHA,'Original cap reply distinct from new budget')
    rows.append((str(ROOT/R.CAP),cap));inputs[str(out/'user-decision.json')]=cap
    if (out/'user-decision.json').exists():
        need(R.read(out/'user-decision.json')==cap,'Own cap byte copy changed')
        rows.append((str(out/'user-decision.json'),cap))
    return Snapshot(_unique(rows),tuple(sorted(inputs.items())),tuple(sorted(generated.items())),encode(manifest),source_sha,
                    Path(out),None,None,None,None,None)


def prepare(out=OUT):
    snapshot=source_snapshot(out);current(snapshot)
    cap=dict(snapshot.inputs)[str(out/'user-decision.json')]
    if not (out/'user-decision.json').exists():R.exclusive(out/'user-decision.json',cap,lambda:current(snapshot))
    snapshot=snapshot._replace(files=_unique([*snapshot.files,(str(out/'user-decision.json'),cap)]))
    D=driver(snapshot)
    record=D.prepare()
    complete=prepared_snapshot(snapshot,D)
    R.exclusive(out/'prepare-evidence.json',encode({'unit':130,'legacy_envelope_unit':119,'source_freeze_sha256':snapshot.source_sha,
        'prepared_sha256':digest(complete.prepared_raw),'run_id':record['run_id'],'nonce':record['nonce'],
        'bundle_sha256':record['bundle_sha256'],'bundle_bytes':record['bundle_bytes'],'native_sha256':digest(generated_bytes(snapshot,'native.py')),
        'contract_config_program_byte_identical':False,'contract_config_byte_identical119':True,'native_exact129':True,
        'program_sha256':digest(generated_bytes(snapshot,'program.json')),'program_delta_paths':parse(snapshot.manifest_raw)['program_delta']['allowed_JSON_paths'],'SDK':0,'SSH':0,'hardware_approved':False}),lambda:current(complete))
    return record


def prepared_snapshot(snapshot,D=None):
    value=R.read(snapshot.out/'prepared.json');record=parse(value)
    need(type(record) is dict and set(record)==set(IDENTITY) and all(type(record[k]) is str and re.fullmatch('[0-9a-f]{32}',record[k]) for k in ('run_id','nonce')),
         'Closed new prepared identity')
    need(type(record['bundle_bytes']) is int and 0<record['bundle_bytes']<=128*1024**2 and
         all(type(record[k]) is str and re.fullmatch('[0-9a-f]{64}',record[k]) for k in ('driver_sha256','bundle_sha256','job_sha256')),'Prepared sizes/hashes')
    run=snapshot.out/'runs'/record['run_id'];R.path_guard(run)
    bundle=R.read(run/'bundle.zip');job=R.read(run/'job.json')
    need(len(bundle)==record['bundle_bytes'] and digest(bundle)==record['bundle_sha256'] and digest(job)==record['job_sha256'],'Captured current bundle/job raw')
    s=snapshot._replace(files=_unique([*snapshot.files,(str(snapshot.out/'prepared.json'),value),(str(run/'bundle.zip'),bundle),(str(run/'job.json'),job)]),
                        prepared_raw=value,bundle=bundle,job_raw=job,record_raw=encode(record))
    current(s)
    if D is None:D=driver(s)
    bind_driver(D,s,lambda:current(s))
    D.verified_payload(run,record)
    current(s)
    return s


def grant_records(out=OUT,active=True,now=time.monotonic):
    permission_raw,e=runtime_permission(out)
    graw=R.read(out/'user-budget-grant.json');rraw=R.read(out/'user-budget-reply.json')
    need(len(graw)<=65536 and len(rraw)<=65536,'Bounded actual budget records')
    g,r=parse(graw),parse(rraw)
    common={'unit','kind','approved','duration_s','hardware_approved'}
    need(type(r) is dict and set(r)==common|{'reply_text','conversation_ref'},'Closed actual130 reply')
    need(type(g) is dict and set(g)==common|{'reply_sha256','source_freeze_sha256','prepared_sha256','started_monotonic','deadline_monotonic','grant_nonce'},'Closed actual130 grant')
    for item,kind in ((r,'ACTUAL_USER_REPLY'),(g,'REVIEWED_V4_VIDEO_RUN_GRANT')):
        need(type(item['unit']) is int and item['unit']==130 and item['kind']==kind and item['approved'] is True and type(item['duration_s']) is int and item['duration_s']==2700 and item['hardware_approved'] is False,'Actual separately permitted130 simulation budget only')
    need(all(type(r[k]) is str and 0<len(r[k].strip())<=16384 for k in ('reply_text','conversation_ref')),'Retained actual new explicit reply')
    token='|permission_sha256='
    need(r['reply_text']==e['reply_text'] and r['conversation_ref']==e['conversation_ref']+token+digest(permission_raw) and r['conversation_ref'].count(token)==1,'Exact new permission rawSHA to actual reply context chain')
    for key in ('reply_sha256','source_freeze_sha256','prepared_sha256'):
        need(type(g[key]) is str and re.fullmatch('[0-9a-f]{64}',g[key]),'Closed grant SHA')
    need(g['source_freeze_sha256']==e['source_freeze_sha256'] and g['reply_sha256']==digest(rraw) and type(g['grant_nonce']) is str and re.fullmatch('[0-9a-f]{32}',g['grant_nonce']),'Same captured new reply/permission/F/nonce')
    start,end=g['started_monotonic'],g['deadline_monotonic']
    need(all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in (start,end)) and end==start+2700,'Root fixed2700, no rearming')
    if active:need(start<=now()<end,'Actual Root period active')
    return Grant(graw,rraw,g['source_freeze_sha256'],g['prepared_sha256'],start,end,g['grant_nonce'],permission_raw)



def run_snapshot(out=OUT,active=True,now=time.monotonic):
    grant=grant_records(out,active,now)
    s=prepared_snapshot(source_snapshot(out))
    need(grant.source_sha==s.source_sha and grant.prepared_sha==digest(s.prepared_raw) and
         parse(grant.permission_raw)['L4_report_sha256']==digest(dict(s.files)[str(out/'review/main-L4-final.json')]),'Actual new permission/grant binds same captured F/L4/prepared bytes')
    s=s._replace(files=_unique([*s.files,(str(out/'user-budget-grant.json'),grant.raw),(str(out/'user-budget-reply.json'),grant.reply_raw),(str(out/'new-runtime-permission.json'),grant.permission_raw)]),grant=grant)
    current(s)
    return s


def write_all(stream,data,end,now=time.monotonic):
    view=memoryview(data);offset=0
    while offset<len(view):
        need(now()<end,'Same fixed transport end')
        n=stream.write(view[offset:]);need(type(n) is int and 0<n<=len(view)-offset,'Partial write progress')
        offset+=n


def _metadata(snapshot,dispatch):
    g=snapshot.grant
    return {'unit':130,'legacy_envelope_unit':119,'source_freeze_sha256':snapshot.source_sha,
        'prepared_sha256':digest(snapshot.prepared_raw),'grant_sha256':digest(g.raw),'reply_sha256':digest(g.reply_raw),
        'new_runtime_permission_sha256':digest(g.permission_raw),'new_runtime_permission':parse(g.permission_raw),
        'grant_nonce':g.nonce,'period_start':g.start,'period_end':g.end,'dispatch_monotonic':dispatch,
        'program_sha256':digest(generated_bytes(snapshot,'program.json')),'program_delta_paths':parse(snapshot.manifest_raw)['program_delta']['allowed_JSON_paths'],
        'record':parse(snapshot.record_raw),'files':{p:{'sha256':digest(b),'bytes':len(b)} for p,b in snapshot.files},
        'actual_prior_SDK':5,'new_SDK_max':1,'retry':0,'hardware_approved':False,
        'task_scope_sha256':digest(dict(snapshot.files)[str(ROOT/'outputs/mp18-video-run-128/task-scope.json')]),
        'goal_allocation':parse(dict(snapshot.files)[str(ROOT/'outputs/mp18-video-run-128/task-scope.json')])}


def _seal(snapshot_raw,metadata):
    return encode({'unit':130,'new_runtime_permission_sha256':metadata['new_runtime_permission_sha256'],'snapshot_sha256':digest(snapshot_raw),'grant_sha256':metadata['grant_sha256'],
        'prepared_sha256':metadata['prepared_sha256'],'source_freeze_sha256':metadata['source_freeze_sha256'],
        'period_start':metadata['period_start'],'period_end':metadata['period_end'],'dispatch_monotonic':metadata['dispatch_monotonic']})


class Owner:
    def __init__(self,snapshot,snapshot_raw,seal_raw,dispatch):
        self.snapshot,self.snapshot_raw,self.seal_raw,self.dispatch=snapshot,snapshot_raw,seal_raw,dispatch
        self.lock,self.sent=threading.Lock(),False
        self.go_raw=None
        self.recovered_rows=()
    def current(self,active=False,now=time.monotonic):
        s=self.snapshot;current(s)
        if self.recovered_rows:R.verify_files(self.recovered_rows)
        need(R.read(s.out/'consumed-snapshot.json')==self.snapshot_raw and R.read(s.out/'admission.json')==self.seal_raw,'Expected in-memory snapshot/seal bytes')
        if self.go_raw is not None:need(R.read(s.out/'GO.json')==self.go_raw,'Own GO original bytes')
        if active:need(s.grant.start<=now()<s.grant.end,'Same active Root period')
    def sender(self,stream,ready,work_end,now=time.monotonic):
        with self.lock:
            s=self.snapshot;g=s.grant
            need(not self.sent and now()<min(self.dispatch+20,g.end,work_end),'First timely GO only')
            expected={k:parse(s.record_raw)[k] for k in IDENTITY}
            need(type(ready) is dict and set(ready)==set(expected)|{'kind','remote_ready'} and ready['kind']=='READY' and
                 {k:ready[k] for k in expected}==expected and type(ready['remote_ready']) in (int,float) and math.isfinite(ready['remote_ready']),'Original closed READY')
            self.current(True,now)
            go=encode({'unit':130,'new_runtime_permission_sha256':digest(g.permission_raw),'grant_nonce':g.nonce,'grant_sha256':digest(g.raw),'prepared_sha256':digest(s.prepared_raw),
                'period_start':g.start,'period_end':g.end,'dispatch_monotonic':self.dispatch,'sent_monotonic':now(),
                'run_id':expected['run_id'],'nonce':expected['nonce'],'GO_count':1,'new_SDK_max':1,'retry':0})
            R.exclusive(s.out/'GO.json',go,lambda:self.current(True,now));self.go_raw=go
            # Required post-exclusive current revalidation before any wire GO.
            self.current(True,now)
            need(now()<min(self.dispatch+20,g.end,work_end),'Current GO fence after proof')
            self.sent=True
            write_all(stream,encode(dict(expected,kind='GO'))+b'\n',min(self.dispatch+20,work_end,g.end),now);stream.flush()
            for i in range(0,len(s.bundle),1024*1024):write_all(stream,s.bundle[i:i+1024*1024],min(work_end,g.end),now)
            stream.flush()


def admit(snapshot,now=time.monotonic):
    s=snapshot;permission_raw,e=runtime_permission(s.out);g=s.grant
    need(type(g) is Grant and g.permission_raw==permission_raw and e['source_freeze_sha256']==s.source_sha,'Same captured new permission required before admission writes')
    need(g is not None and g.start<=now()<g.end and g.end-now()>2402,'Actual Root active2402 headroom before RPC')
    current(s);record=parse(s.record_raw);run=s.out/'runs'/record['run_id']
    for p in (s.out/'admission.json',s.out/'consumed-snapshot.json',s.out/'attempt.json',s.out/'GO.json',s.out/'transport',s.out/'run-result.json',
              run/'retrieved',run/'retrieved.zip',s.out/'native-result.json'):
        R.path_guard(p);need(not p.exists(),'Duplicate new130 admission/GO/result')
    dispatch=now();metadata=_metadata(s,dispatch);snap=encode(metadata);seal=_seal(snap,metadata)
    R.exclusive(s.out/'admission.json',seal,lambda:current(s));R.exclusive(s.out/'consumed-snapshot.json',snap,lambda:current(s))
    owner=Owner(s,snap,seal,dispatch)
    owner.current(True,now);R.path_guard(s.out/'transport').mkdir(exist_ok=False)
    return owner


def offline_owner(out=OUT):
    # Period expiration is not rearmed and does not prevent source-bound offline verification/encoding.
    s=run_snapshot(out,active=False)
    snap=R.read(out/'consumed-snapshot.json');meta=parse(snap)
    expected=_metadata(s,meta['dispatch_monotonic'])
    need(meta==expected,'Offline consumed identity matches actual canonical grant/prepared/F')
    seal=_seal(snap,meta);need(R.read(out/'admission.json')==seal,'Offline expected admission seal')
    owner=Owner(s,snap,seal,meta['dispatch_monotonic'])
    need((out/'GO.json').exists(),'Offline native result requires original GO attempt')
    go_raw=R.read(out/'GO.json');go=parse(go_raw);record=parse(s.record_raw)
    need(go.get('unit')==130 and go.get('new_runtime_permission_sha256')==digest(s.grant.permission_raw) and go.get('grant_nonce')==s.grant.nonce and go.get('grant_sha256')==digest(s.grant.raw) and
         go.get('prepared_sha256')==digest(s.prepared_raw) and go.get('run_id')==record['run_id'] and go.get('nonce')==record['nonce'] and
         go.get('period_start')==s.grant.start and go.get('period_end')==s.grant.end and go.get('dispatch_monotonic')==meta['dispatch_monotonic'] and
         go.get('GO_count')==1 and go.get('new_SDK_max')==1 and go.get('retry')==0 and
         type(go.get('sent_monotonic')) in (int,float) and math.isfinite(go['sent_monotonic']) and
         s.grant.start<=go['sent_monotonic']<min(s.grant.end,meta['dispatch_monotonic']+20),'Offline original GO identity')
    owner.go_raw=go_raw
    owner.current(False)
    if (out/'result-receipt.json').exists():
        owner.recovered_rows=capture_recovered(owner)
        owner.current(False)
    return owner


def capture_recovered(owner):
    # Preserve exact recovered members before any subsequent offline consumer/encoder write.
    s=owner.snapshot;record=parse(s.record_raw);run=s.out/'runs'/record['run_id']
    receipt_raw=R.read(s.out/'result-receipt.json');receipt=parse(receipt_raw);archive=R.read(run/'retrieved.zip')
    need(type(receipt) is dict and set(receipt)=={'unit','run_id','nonce','archive_sha256','archive_bytes','native_consumer_exit'} and
         receipt['unit']==130 and receipt['run_id']==record['run_id'] and receipt['nonce']==record['nonce'] and
         receipt['archive_bytes']==len(archive) and receipt['archive_sha256']==digest(archive),'Current recovered archive receipt')
    rows=[(str(s.out/'result-receipt.json'),receipt_raw),(str(run/'retrieved.zip'),archive)]
    D=driver(s)
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        infos=z.infolist();need(infos and len(infos)==len({i.filename.casefold() for i in infos}) and
            sum(i.file_size for i in infos)<2*1024**3,'Current recovered unique bounded members')
        for item in infos:
            D._safe_name(item.filename)
            need(not item.is_dir() and item.flag_bits&1==0 and (item.external_attr>>16)&0o170000!=0o120000,'Current recovered member role')
            p=run/'retrieved'/item.filename;value=R.read(p)
            need(value==z.read(item),'Current exact recovered member bytes')
            rows.append((str(p),value))
    return tuple(rows)


def result_path(owner,path):
    owner.current(False);s=owner.snapshot;record=parse(s.record_raw);run=s.out/'runs'/record['run_id'];p=Path(path)
    need(p==s.out/'native-result.json' or p==run or p.is_relative_to(run),'Closed new130 result role')
    R.path_guard(run);R.path_guard(p);need(run.resolve()==run and p.resolve().is_relative_to(ROOT),'Original result anchor unchanged')
    return p


def consume_archive(owner,wire,D=None):
    s=owner.snapshot;record=parse(s.record_raw);run=s.out/'runs'/record['run_id']
    current(s)
    ready_raw,header_raw,archive=wire.split(b'\n',2);ready=parse(ready_raw);header=parse(header_raw)
    expected={k:record[k] for k in IDENTITY}
    need(type(ready) is dict and set(ready)==set(expected)|{'kind','remote_ready'} and ready['kind']=='READY' and
         {k:ready[k] for k in expected}==expected and type(ready['remote_ready']) in (int,float) and math.isfinite(ready['remote_ready']),'Recovered READY identity')
    need(type(header) is dict and set(header)=={'kind','run_id','nonce','bytes','sha256'} and header['kind']=='RESULT' and
         header['run_id']==record['run_id'] and header['nonce']==record['nonce'] and type(header['bytes']) is int and
         0<header['bytes']<=2*1024**3 and len(archive)==header['bytes'] and digest(archive)==header['sha256'],'Closed RESULT bytes/hash/nonce')
    if D is None:D=driver(s)
    bind_driver(D,s,lambda:owner.current(False))
    D.verified_payload(run,record)
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        infos=z.infolist();need(bool(infos) and len(infos)==len({i.filename.casefold() for i in infos}) and sum(i.file_size for i in infos)<2*1024**3,'Unique bounded result ZIP')
        for i in infos:
            D._safe_name(i.filename);need(not i.is_dir() and i.flag_bits&1==0 and (i.external_attr>>16)&0o170000!=0o120000,'No result links/encrypted entries')
        need({'process.json','recovery-seal.json'}<={i.filename for i in infos},'Original result records')
        destination,archive_path=run/'retrieved',run/'retrieved.zip';paths=[destination/i.filename for i in infos]
        for p in (destination,archive_path,s.out/'native-result.json',*paths):result_path(owner,p)
        need(not destination.exists() and not archive_path.exists() and not (s.out/'native-result.json').exists(),'First recovery only')
        need(z.testzip() is None,'Complete archive CRC')
        result_path(owner,destination).mkdir(exist_ok=False)
        R.exclusive(result_path(owner,archive_path),archive,lambda:owner.current(False))
        for i,p in zip(infos,paths):
            data=z.read(i);result_path(owner,p).parent.mkdir(parents=True,exist_ok=True)
            R.exclusive(result_path(owner,p),data,lambda:owner.current(False))
    result_path(owner,s.out/'native-result.json')
    code=D.verify_native_result(run,record,destination)
    R.exclusive(s.out/'result-receipt.json',encode({'unit':130,'run_id':record['run_id'],'nonce':record['nonce'],
        'archive_sha256':digest(archive),'archive_bytes':len(archive),'native_consumer_exit':code}),lambda:owner.current(False))
    return code


def consume(out=OUT):
    owner=offline_owner(out);s=owner.snapshot;record=parse(s.record_raw);run=out/'runs'/record['run_id']
    if not (run/'retrieved').exists():return consume_archive(owner,R.read(out/'transport/stdout.txt'))
    receipt=parse(R.read(out/'result-receipt.json'));archive=R.read(run/'retrieved.zip')
    need(receipt['run_id']==record['run_id'] and receipt['nonce']==record['nonce'] and receipt['archive_sha256']==digest(archive),'Original recovered archive identity')
    D=driver(s);bind_driver(D,s,lambda:owner.current(False));result_path(owner,out/'native-result.json')
    return D.verify_native_result(run,record,run/'retrieved')


def guarded_media_invoke(owner, invoke):
    def checked(argv, timeout=120):
        owner.current(False)
        return invoke(argv, timeout=timeout)
    return checked


def encode_video(out=OUT):
    owner=offline_owner(out);s=owner.snapshot;current(s)
    data=generated_bytes(s,'media.py');media=R.load_raw('media130_checked_'+str(id(s)),data,DERIVED/'media.py')
    media.D.OUT=out;media.OUT=out
    bind_driver(media.D,s,lambda:owner.current(False))
    media.invoke=guarded_media_invoke(owner,media.invoke)
    return media.encode()


def load_proxy():
    value=R.read(ROOT/R.PROXY);need(digest(value)==R.PROXY_SHA,'Accepted123 raw stdin proxy pin')
    return R.load_raw('proxy123_for130',value,ROOT/R.PROXY)


def run(out=OUT):
    s=run_snapshot(out,active=True);D=driver(s)
    cfg=parse(generated_bytes(s,'config.json'));item=cfg['refs']['winjob.py'];helper_raw=R.read(ROOT/item['path'])
    need(digest(helper_raw)==item['sha256'],'Original WinJob helper')
    helper=D.load_module('winjob130_local',helper_raw,ROOT/item['path']);proxy=load_proxy()
    owner=admit(s);g=s.grant;record=parse(s.record_raw)
    bind_driver(D,s,lambda:owner.current(False))
    remaining=g.end-time.monotonic();args=dict(record,remote_root=cfg['remote_root'],remaining=remaining)
    literal=R.thin_bootstrap(generated_bytes(s,'driver.py'),generated_bytes(s,'contract.py'),args)
    command=proxy.proxy_command(str(Path(cfg['sdk']['isaac_root'])/'kit/python/python.exe'),literal,remaining)
    import os
    ssh=Path(os.environ['SystemRoot'])/'System32/OpenSSH/ssh.exe'
    argv=[str(ssh),'-o','BatchMode=yes','-o','ConnectionAttempts=1','-o','ConnectTimeout=10',cfg['ssh_alias'],command]
    R.exclusive(out/'attempt.json',encode({'unit':130,'dispatch_monotonic':owner.dispatch,'period_start':g.start,'period_end':g.end,
        'grant_sha256':digest(g.raw),'run_id':record['run_id'],'actual_prior_SDK':5,'new_SDK_max':1,'retry':0,
        'pipeline_SSH_launch_attempts':1}),lambda:owner.current(True))
    def sender(stream,stdout_path,work_end):
        ready=None
        while time.monotonic()<min(owner.dispatch+20,work_end):
            b=stdout_path.read_bytes()
            if b'\n' in b:ready=parse(b.split(b'\n',1)[0]);break
            time.sleep(.01)
        owner.sender(stream,ready,work_end)
    process=None
    try:
        process=helper.run(argv,out/'transport',g.end-time.monotonic()-2,cleanup_s=2,input_sender=sender)
        R.exclusive(out/'transport.json',encode(process),lambda:owner.current(False))
        need(process['raw_complete'] and process['terminal'] and process['child_state']=='REAPED' and process['job_active_after']==0 and
             process['actual_child_exit_code']==0 and not process['timed_out'],'Actual proxy lifetime complete/reaped')
        code=consume_archive(owner,R.read(out/'transport/stdout.txt'),D)
    except BaseException as exc:
        R.exclusive(out/'run-result.json',encode({'unit':130,'status':'FAIL','phase':'TRANSPORT_OR_RESULT','error':type(exc).__name__+': '+str(exc),
            'actual_prior_SDK':5,'new_SDK_initializations':'UNKNOWN' if (out/'GO.json').exists() else 0,'new_SDK_max':1,'retry':0,
            'pipeline_SSH_launch_attempts':1,'process':process,'run_id':record['run_id'],'period_end':g.end,'hardware_approved':False}),lambda:owner.current(False))
        raise
    R.exclusive(out/'run-result.json',encode({'unit':130,'status':'PASS' if code==0 else 'FAIL','native_consumer_exit':code,
        'actual_prior_SDK':5,'new_SDK_max':1,'retry':0,'pipeline_SSH_launch_attempts':1,'run_id':record['run_id'],
        'period_start':g.start,'period_end':g.end,'finished_monotonic':time.monotonic(),'hardware_approved':False}),lambda:owner.current(False))
    return code


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('role',choices=('prepare','run','consume','encode'))
    role=parser.parse_args().role
    value={'prepare':prepare,'run':run,'consume':consume,'encode':encode_video}[role]()
    print(json.dumps(value,ensure_ascii=False));raise SystemExit(value if type(value) is int else 0)
