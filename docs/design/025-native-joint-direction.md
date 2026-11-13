> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 025 / ND-20261024 — CAD 관절 실제 회전과021코어 실행 대조

2026-10-24。사용자 최신 지시로 실행한다.

## 범위와 권한

확정 저장 v2 `models/armold-mks-product-v2/armold-type-mks-product-v2.solidcraft`의 복사본을 설치된 SolidCraft CLI 실제 --version 0.20.0 (폴더명0.18.2와 다름, exe SHA256 fa17c35d53443c5bd91dfe6cf648d46aa8151869d2259948ae2f101098340538) `joint.drive`로 실제 구동한다. 승인021 코어의 FK와 저장 표시0 기준 기하 변환을 대조한다. 원본/models/기존021·023·SB 소스/출력/펌웨어는 무수정. 링/접촉/간섭/강도/치형·motor/CAN 방향·물리 영점/한계·Isaac 수용 제외. CLI 원본과 snapshot 입력 해시를 보존한다. 새 소유 경로: src/native_direction/, outputs/native-direction-v1/, .dev/native-direction-evidence/, 이 계획 및 최소 인계/구조지도 갱신.

## 검토와 이월 원장

L1→비작성자 L2→L3→비작성자 L4. 각각 최대2회, 첫 검토 전 선언. 같은 검토 완료 후 추가 렌즈/번호변경으로 예산을 초기화하지 않는다. 기존020/023 startup/input/result-finalization EXHAUSTED와 SB의 다음 추가 동일 class 독립측정·작성자 수용 재발1개 즉시 EXHAUSTED 임계 유지.021 math/023 dependency CLOSED, firmware first-fault 임계 유지. 링 indexed-geometry 미해결 보류. 이번은 native solver의 occurrence rigid placement만 대상으로 하며 indexed body/ring 검증 재개가 아니다. 외부계열은 기존 중앙 bridge 차단으로 NOT_RUN, 우회 없음. 동일계열 비작성자 독립 검토와 잔여 위험 구분.

## 측정 설계

- CLI --help/commands와 읽기전용 component.list/joint.inspect/joint.list preflight를 실제 확인했다.6 revolute·Base grounded·나머지7개 root occurrence의 초기 rigid transform identity·저장값0을 관측했다. 관찰만으로 방향을 단정하지 않는다.
- 읽기전용 승인 SB verify와 고정021 승인 receipt/manifest/run/source hash를 확인한 후, 정확한 승인 source bytes만 compile한다. 승인 baseline에 없는 core/모델을 자동 채택하지 않는다. native/kin/core/CLI hash는 실행 전후 동일해야 한다.
- 초기0,6축별 +5/-5/+30/-30도(24), mixed두 자세 및 모든축0으로 복귀 경로를 측정. 각 case는 새 원본 복사에서6개 drive를 순서대로 실행; drive 전후 component.list/joint.inspect/joint.list 결과와 stderr/exit를 원문 보존한다. mixed는[15,-20,25,10,-15,20] 및 반대값. 기준시점과 복귀도 실제 solve를 거친다. clamp/오류/conflicts/floating/누락/중복/nonfinite/shape불일치/timeout/nonzero이면 불수용.
- core FK의 p_i(q),R_i(q)는 링크 frame. CAD occurrence는 세계좌표로 만들어진 body 집합을 움직이는 rigid placement다. 따라서 예측은 R=R_i(q)*transpose(R_i(0)), t_mm=1000*(p_i(q)-R*p_i(0)). 원점 수치만 비교하지 않고 각 Base/Link1..6의 전체3x4행렬을 관측과 대조한다. 회전성분1e-7, 위치성분1e-4mm 허용; 양부호 모두 고정 +1 매핑을 먼저 시험하고 반대부호를 임의로 자동 채택하지 않는다. 불일치시 mismatch표·관측을 남기고 BLOCK한다.
- joint.inspect 양끝 resolves/frame·joint.list requested actual degree/axis/anchor 및 grounding 상태도 확인. 정지한 ancestor/Base 불변, descendants의 위치/회전 전파도 전체 행렬 비교가 보장한다. 유효값만 쓰고 170deg model limit/소프트 limit를 물리 한계로 해석하지 않는다.
- 결과는 실행한 SolidCraft 버전/hash와 입력 모델 hash에만 결속한 OFFLINE_NATIVE_DIRECTION_CANDIDATE. 모터 부호로 전달하지 않는다. 실제 body vertices/mesh나링 형상은 읽어 판정하지 않는다.

## 오류/출판 경계

기존 SB entrypoint/contract는 변경하지 않는다. 새 검사는 공용 library/범용 generator가 아닌 명시적root/CLI를 받는 유한한 offline 측정 script다. stdlib 부모가 repo 의존성 읽기 전 새 출력 current BUILDING을 기록하고 try/finally 실패시 FAILED; child는 sandboxed copy에서 실행. 정상 Python/온전한 부모/쓰기 가능한 저장소/단일 writer 신뢰범위를 명시한다. restore만으로 verify 회복 또는 과거PASS fallback 금지. current PASS는 생성무결성, 별도 L4/disposition이 수용이다. 시작경계 재발도 L4 전체 관할에서 기존 임계 적용.

## 검증/완료

실제 정상 대조와 실패주입(누락 core/native, CLI nonzero/timeout, malformed 측정, 잘못된 axis/부호/deg-rad/하위전파 행렬) 검증. 생산 판정함수에 회전부호반전/회전검사누락/위치검사누락의 compiled 행동변형이 실제 음성데이터를 통과시키면 원 시험이 실패하는지 확인. 원본 positive 먼저 PASS. 기계적 compile/광범위except 무시0/입력전후 해시 → L4 전체 구현·CLI·출력·원장 검토. 불일치면 자동 CAD/코어 수정하지 않고 관측과 원인/후속을 기록한다. 완료시 HANDOFF/SESSION/LESSONS·로컬 scoped commit, push없음.

## L2 R1 처분 및 실행 해석

ND-L2-R1-1 수용: 설치 폴더명으로 추정한 버전0.18.2를 실제 --version0.20.0/실제exe hash로 정정했다. R1 원문 보존, statement/provenance 최초 지적이며 startup/ring 임계로 혼용하지 않는다. L2R2가 마지막 예산이다.

실제 J1+5 preflight는 core+5와 반대 회전이었다. 이 관측 때문에 양성 시험은 ‘측정자료 정상 처리 + 기대되는 불일치 거절’의 테스트suite PASS를 뜻하며, actual+1일치PASS가 아니다.27자세(0+24축별+mixed2)를 모두 측정한 뒤 공식+1대조 mismatch를 report BLOCK/current FAILED/exit1로 남긴다. core 입력 전체부호반전 대조는 별도의 진단 가설 수치로만 함께 기록하며 자동 매핑/코드/CAD/제어 채택은 하지 않는다. 각 mixed/단축 case를 측정한 동일 CLI 메모리 상태에서6축0으로 실제 drive/solve한 복귀 행렬도 대조한다. 정상 관측 보고서는 불일치가 있어도 원문과 해시를 보존하고, 데이터/실행 실패는 별도 FAILED reason으로 구분한다. 모델 해시가 달라지면 기존 관측을 새 리비전으로 일반화하지 않는다.
