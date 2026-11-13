> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 056 — Torch 파일 출처와 동적 namespace를 분리한 진단 계약

2026-10-28 사용자 「진단 검증기까지 계속진행해 해결해」에 따라055 실제 실패의 표현 계약을 수정하고 실제 진단·조건부 IsaacLab 연결까지 검증한다. 재부팅/설치/전역설정/실물 보정/모터/CAN/플래시/학습/구매/CAD 변경은 제외한다. 질량·관성 가정,047 미해결, 링 보류는 유지한다.

## 소유·한도·이전 이력

M8/45분, 시작13:43UTC. 소유는 이 계획과 `src/simulation/inventory_session/{session.py,providers.py,worker.py,settings.json,launch.ps1,test_session.py,README.md}`, 근거는 `outputs/isaac-inventory-v1/`다. L2/L4 각 최대2회, 비작성자 읽기 전용 독립 검토만 사용한다. 이전 외부계열 bridge hook 차단은 재시도/우회하지 않고 동일계열 fallback 잔여 위험을 명시한다. 작성자 단독 최종검수는 하지 않는다. .dev/BOM/CAD/펌웨어/기존053~055 source·결과 무수정, 소유 파일만 로컬 commit한다.

055의 소비 원장 SHA2bd754ba47baee7bf6dc3fc950b405f4b1eaa0ef6f54304bc6723d245f07fd8d와 원본 nested054/053를 새 원장에 불변 보존한다.055 감사1·진단1실패·연결0과 L4 3/3은 그대로며 성공으로 재분류하지 않는다. 새 사용자 권한과 새 **객체 종류별 관측 계약**에 따른056 audit900s/진단300s/조건부 연결600s 각각1회다. 단순 이름/카운터 변경으로055를 재실행하지 않는다. 실제 단계 실패 시 같은 목적 재시도나 추가 수리출하 없이 근거·정리 결과를 남긴다. 기존 provenance7/physical-frame6 EXHAUSTED, eligibility2/다음 독립실측+작성자수용 동일 누락1 충분 임계는 불변이다. L2/L4에 class·착지·예산 종결/소진 판단과 새 계약의 정당성 판정을 요구한다.

## 실제 원인과 새 관측

055의 파일 보고 Torch977개 중 `torch.ops=_ops.py`, `torch.classes=_classes.py`가 절대경로 검사에서 실패했다. 실제 SDK `_Ops`/`_Classes` ModuleType 소스가 해당 값을 명시 설정함을 SHA·행 문맥으로 확인했다. SDK Torch2.11.0+cu128/CUDA12.8의 GPU6은 성공했고, 진단 완료 report는 작성되지 않았다. 이를 연결 허가로 재사용하지 않는다.

새 producer는 실제 로드된 Torch 객체에 대해 기존 raw `loaded_torch_modules`(비어 있지 않은 reported-file을 가진 항목)와 같은 key 집합의 `torch_inventory`를 추가한다. 행마다 module_id, reported_file, spec_origin(nullable), loader의 type module/qualname(nullable), 객체 type의 module/qualname, type 정의 모듈의 실제 파일·module_id(nullable), 그 정의 모듈의 클래스 객체와 실제 type이 동일한지 boolean을 기록한다. 판정용 kind flag를 producer가 정해 root에 믿게 하지 않는다. raw __file__을 cwd/prefix와 합쳐 가짜 절대경로로 만들지 않는다.

reported-file이 없는 객체는 별도 fileless name→id 목록과 전체 Torch 객체 수로 관측 범위를 명시한다. 이 목록은 파일 출처를 증명하지 않으며 원055도 파일 보고 객체만 경로 검사했다. 이 변경으로 파일 없는 객체의 실행/파일 출처를 검증했다는 주장은 하지 않는다. 실제 파일 보고 행의 누락·추가, 두 목록 겹침, 전체 개수 불일치는 거절한다.

root와 producer의 같은 validator가 raw string map↔행 map의 전수 key/파일값을 결속하고, torch 본체의 module_id/origin을 기존8module 관측표와 대조한다. namespace와 type 정의 모듈의 ID는 같은 typed snapshot 안에서 교차참조한다. producer는 실제 객체의 id와 `vars(definition_module)[class_name] is type(namespace_object)`를 측정한다. 이는 별도 독립 ID attestation이 아니며, root는 hash/PID로 묶인 고정 producer의 관측을 신뢰한다. opaque ID를 내부 관계가 그대로인 채 모두 일관되게 재명명한 완전 위조 record를 root가 탐지한다고 주장하지 않는다. 일반 파일 보고 행은 reported_file이 절대경로여야 하고 spec_origin이 있으면 같은 정규화 파일이어야 한다. 절대 파일 출처의 범위 검사와 진단 완료의 구조 완결성 검사는 분리한다: 다른 실제 provider의 완전한 관측은 진단에는 허용하고 BASELINE/최종 연결에는 허용하지 않는다.

상대 파일 보고는 임의 예외가 아니다. 정확한 두 동적 namespace만 허용하되 각각 이름/relative marker/type module+qualname/실제 type 정의 class binding을 함께 확인한다. `torch.ops`는 `torch._ops._Ops`, `torch.classes`는 `torch._classes._Classes`여야 한다. type 정의 모듈이 **같은 inventory의 파일 보고 행**으로 존재해야 하고, 그 행의 module_id·실제 파일이 type 정의 관측과 같아야 한다. 정의 파일은 실제 torch 본체 옆 `_ops.py`/`_classes.py`이어야 한다. namespace spec은 null이며 loader 관측은 명시적으로 기록한다. 이름만 맞는 일반 ModuleType, 잘못된 type, 누락된 정의 행, 다른 root, 상대 일반 모듈/경로 순회/알 수 없는 namespace는 실패다.

최종 연결에서는 모든 파일 보고 행·동적 type 정의·torch 본체/version/C extension을 의도한 canonical048 prefix에 묶는다. SDK NumPy2.3.1/SciPy1.17와 Warp1.17은 보존하고 prefix Torch2.11.0+cu130/Torchvision0.26.0+cu130/CUDA13/GPU6,8provider·app 전후5객체 identity, 고정 CAD4facet/10step11행 수학은 그대로 필수다. CUDA13을 삭제하거나 현재 CUDA12.8 관측을 완전 진단으로 승격하지 않는다.

## 경계 재사용·검증

055의 byte-cache/single-read/공개PS→isolated hash loader, actual/policy/shell/transport, 단발 reservation, nested proof, 허가 수명300초를 내용으로 재사용한다.056이 새로운 typed inventory를 소유하고 기존055 public/entry/consume는 호출하지 않는다. 새 source-package와055 원장/배달결과 SHA를 고정한다. 감사는 SDK import0/full seal이고 새 source 진단은 같은 audit source-signature에서만 허가한다. 최종 조회가 과거 감사 허가를 현재 시각으로 다시 만료시키지 않는다. PREAPP은 새 프로세스에서 SDK bootstrap→SDK numeric→SDK Warp→prefix Torch/TV→App이며 unload/reload나 설치 변경은 없다.

호스트는 기존9개 시험과 실제 child7/timeout actual1-policy124를 보존한다. 실제055 raw977 inventory를 그대로 보존하고, 추가 metadata는 HOST MODEL로만 표시한다. 실제 모듈을 이용한 producer→validator 정상 동적 namespace/정의 행 positive, 같은 이름인 보통 모듈·정의 ID 불일치·ID 둘을 함께 맞춰도 잘못된 정의 파일/타입인 경우·일반 상대경로·spec 불일치·다른root·누락/추가/개수·fileless 겹침 negative를 검증한다. 누락이 profile fallback으로 허가되지 않아야 하고 root consume 실제 경로의 resealed provider artifact에서도 거절되어야 한다. source AST/scoped whitespace/L4 뒤에만 실제3목적을 각1회 실행한다. SDK가 없는 호스트 합성값과 실제 원격 객체 관측을 구분한다. reviewer는 파일 읽기/receipt만 하며 executable reproduction을 생성·실행하지 않는다.
