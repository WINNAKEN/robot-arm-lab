> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 113 후보 — 결정 입력의 형식별 숫자 검증 경계를 새로 설계

2026-11-05 KST. **제안만: 새 범위·예산 승인 대기, source0/HOST0/L2·L4·SSH0/native0.**
112의 마지막 코드 검토에서 확인한 URDF 숫자 경계 결함을 재상정한다.
112를 다시 고치는 R3 또는 남은 작성 시간을 새 권한으로 전환하는 안이 아니다.
아직 시작하지 않은112 조건부 원격45분도 이 후보에 자동 전용하지 않는다.

## 재상정할 관측과 소진 경계

112는 L2R2 PASS12/0 뒤 구현했고, root HOST87(B26/C40/D21)이 통과했다.
R1의 JSON 숫자 반례3종은 수리되어 최종 독립 검증에서 닫혔다.
그러나 required URDF inertia `ixx="inf"`와 영향을 받는4개 입력의 해시·길이를
정합하게 재결속하면, 실제 고정 oracle의 ET 파서가 Base 관성에 inf/nan을
만든 상태로 실제 전건 producer8192/6241와 receipt consumer가 모두 수용한다.
주·보조 독립 생산 receipt SHA는
`37e22b12e205d01a5fb7fc9911b3ffbd055f14d31dba07fa1d961436b5669bb0`로 일치했다.
유한한 같은 값의 다른 표기는 정상 대조군으로 통과했다.

현재 정상 production receipt `b9d81443...`를 그대로 기대하면 변조 입력은
일치 검사에서 거절된다. 이 결함을 native 권위 우회·실제 물리 gate 완화·
quasistatic 계산 오류나 전체 시뮬레이션 불가능으로 확대하지 않는다.
문제는 key47 결정 입력의 비유한 수 거절 계약이8개 JSON에서 끝난 것이다.

112-MAJOR-02(JSON)와112-MAJOR-03(ET로 파싱한 URDF)은 같은
`PREFLIGHT_DECISION_NUMERIC_SCHEMA_NOT_ENFORCED` class의 distinct2다.
R1에 사전 선언한 충분 임계에 따라 현재 D 숫자 검증·지원 시험 source가
소진되는 사안이다. 원 reuse class112-MAJOR-01의 실제 HOST CODE 폐쇄1/0,
JSON instance의 수리 폐쇄, 다른 과거 원장과 모든 실패 원문은 보존한다.
최종 정본은112 `review/L4-r2.json`과 `review/lens-L4-r2/report.json`이다.

## 조사한 대안과 선택

| 대안 | 처분과 이유 |
|---|---|
| 현재 validate.py에 URDF 한 필드 검사 추가 | 현재 source 소진·마지막 회차를 우회하고 형식 경계를 그대로 두므로 채택하지 않음 |
| 기존 native 물리 검사에서만 거절 | 정적 producer/consumer의 명시 입력 계약이 남으며 실제 SDK 실행을 소모하므로 채택하지 않음 |
| 별도 형식별 typed artifact policy와 시험을 새로 작성 | 결정 숫자 전체의 위치·형식·소비 경계를 먼저 닫고 동일 바이트에 적용하는 새 설계 후보로 선택 |

새 policy는112의 숫자 검사 구현을 파일명만 바꿔 가져오지 않는다.
112 소진 source·시험은 읽기 전용 반례와 비교 입력으로만 보존한다.
원 물리 함수45개·workspace/oracle 전건 의미·검사 임계는 그대로 유지한다.
영수증과 provider 어댑터는 새 계약에 맞춰 작성하며 숫자 역할 판정은
새 policy 한 곳이 소유한다. 정상 데이터의 숫자나 모델을 바꾸지 않는다.

## 승인 후 L1/L2에서 먼저 닫을 새 계약

1. 결정 파일의 형식을 전건 분류한다. 현재 model16은 JSON3/URDF1/STL11/README1이다.
   ref와 config/program을 합친 JSON8, URDF의 물리·기구·시각 숫자 속성,
   STL11의 법선·정점 부동소수 값을 형식에 맞게 검증한다. README와 고정
   실행 source는 해시로 결속된 불투명 자료이며, 주석 속 문자열을 수치로
   해석하는 정규식 검사는 하지 않는다. 미분류 결정 필드/형식의 처분과
   필수 필드·배열/행렬 길이를 L2 전에 명시한다.
2. JSON의 정수·유한 실수·논리값 역할은 승인된 독립 스키마로 정한다.
   후보 입력의 현재 타입에서 기대 타입을 만들지 않는다. overflow,
   bool-as-number, 숫자 자리에 들어온 문자열/null·누락·컬렉션 변형을 거절한다.
3. URDF에서는 원 ET 소비자가 읽는 mass/inertia/origin/axis/limit뿐 아니라
   선언된 geometry/material 수치까지 typed finite 파싱한다. inertia6성분·
   xyz/rpy/rgba 등 형상 길이를 닫고 누락과 미분류 숫자 속성을 명시 처리한다.
   finite 검증과 양의 관성/질량 등 원 물리 검증을 구분하며 새 물성 가정을
   만들거나 원 gate를 완화하지 않는다.
4. STL은 실제 binary/ASCII 형식을 판별하고 개수·길이·좌표/법선의 유한성을
   전건 확인한다. 숫자를 고치거나 remesh하지 않는다. 원 모델16 bytes는 그대로다.
5. producer와 consumer는 같은 immutable byte bundle에 같은 policy를 매번
   적용한다. policy의 실제 실행 raw SHA와 정확 입력 source를 결속한다.
   policy 미로딩/다른 코드·해시/생략·오래된 coverage는 거절한다.
   consumer는 full sampling을 재실행하지 않는다.
6. receipt는 기존11키에 `numeric_contract`를 더한 closed12키 후보로 정의한다.
   해당 필드는 policy버전/실제 source SHA/입력 key/형식별 검사 범위를 결속하며
   PASS 문자열이나 호출자가 조립한 coverage를 권위로 쓰지 않는다.
   알고리즘 pin에는 새 policy도 포함한다. 최종 API와 정확 field/type은 L2에서 고정한다.
7. 원 token/thread/parent/end 수명과 B→C→D 매 사용 현재 입력 재읽기를 보존한다.
   policy도 실제 source inventory와 B의 현재 권위 아래에 있어야 한다.
   local closed-return audit는 별도 local Fence를 쓰며 remote Runtime을 만들지 않는다.

## 제안 소유와 새 예산

새 SRC=`src/simulation/typed_decision_preflight_113`,
OUT=`outputs/typed-decision-preflight-113`. 현재112 및 이전 source는 수정하지 않는다.
전체10파일/L10을 S2/S4/S4로 분할하는 후보이며 그룹별로 첫 소스 쓰기부터
구현·HOST·root 귀속 검증·수리를 누적한다. L4 대기 시간만 분리한다.

| 그룹 | 소유 파일과 책임 | 제안 누적 cap |
|---|---|---|
| B2/S2 | bootstrap.py, test_bootstrap.py: 새 unit·source21·typed receipt·권위·실제 명령 길이 |1500초|
| C4/S4 | driver.py, config.json, test_driver.py, OUT execute.py: policy 배선/source21·매 사용 수명·원 물리와 실패/회수 |1500초|
| D4/S4 | validate.py, test_validate.py, decision_schema.py, test_decision_schema.py: 새 형식별 policy와 독립적인 계약 시험·전건/재사용 어댑터 |2400초|

D의40분은 별도 policy·시험까지4파일인 새 작업 예산의 제안이다.
112의25분을 자동 연장하지 않는다. L2/L4는 각각 최대2회,
각 비작성자 main/lens 검토는2700초 cap, 마지막 뒤 R3는 없다.
작성자가 자기 코드 PASS/소진 면제를 선언하지 않는다. 기존 명시 same-family
비작성자 폴백과 공통편향을 유지하며 bridge 수리·설치·새 모델 비용은 포함하지 않는다.
이전 numeric class의 연속 union2/open1·현재 source 소진 이력은 유지하고,
새 설계의 폐쇄 판단과 다음 distinct 재발 임계를 첫 검토 안에서 사전 명시한다.

제안 census는 runtime21=원 immutable15+새bootstrap/driver/config/validate/policy5+
exact helper1, key48=source21+model16+ref11이다. immutable deps46+receipt1=47,
mutable10+metadata5+manifest1로 capsule63, import input은 key48+receipt1=49다.
실제 L1에서 경로·길이·해시·group별 전건 census를 닫고 L2 PASS 전 source0을 유지한다.
source 수를 늘려도 원 helper SHA와 실제 완성 SSH argv8000 미만 검사는 유지한다.

112의 AUDIT-112-R2-01도 설계 입력으로 보존한다. 새 freeze는 이전 객체를
통째로 복사하지 않고 현재 source/dependency/실제 HOST 결과에서 명시 생성한다.
요약 receipt SHA와 dependency의 실제 SHA, HOST 개수와 실행 원문을 서로 대조하고,
시각은 기록한 사건에만 붙인다. 검토 후 원문을 고치는 대신 검토 전 불일치를 거절한다.

## 필수 검증과 조건부 실제 실행

- 원 JSON3variants와 새 URDF ixx inf/nan/overflow 전부를 실제 full producer와
  독립 기대값 consumer에서 재현한다. 정합하게 재결속한 HOST receipt와
  변경하지 않은 실제 production pin 대조를 분리한다. hash 불일치만으로
  숫자 guard 효과를 세지 않는다.
- JSON8·URDF 숫자 역할·binary/ASCII STL의 모든 형식 계층에서
  비유한/타입/누락·추가/길이·컬렉션 반례와 유한·논리값 정상 대조를 둔다.
  실제 parser가 읽는 위치와 coverage의 대응을 확인한다. 숫자가 검사되지
  않은 새 계층이 나타나면 같은 class 판정 대상으로 올린다.
- 원 realpath full과 memory full의 data/metrics가 같고, memory full에서
  real FS 접근0·8192/6241 전건·원45 물리 함수 AST/임계 보존을 확인한다.
- 실제 B→D, C→B→D 같은 D 두 번째 호출과 policy 미배선/변조/생략,
  현재 job/ref/source/receipt/policy 변경, 다른 thread/닫힌 원 token,
  block·종료·UNKNOWN·raw EOF를 비작성자가 관측한다.
- 모든 코드 PASS 뒤 실제 root의 무승인 실행 거절을 먼저 확인한다.
  이후에만 새 unit113·정확 최종 pins에 묶인 **새 첫 원격2700초 단일 시도**를
  시작하는 조건부 권한을 요청한다. import1→정지1 통과→42초 motion1,
  배치/회수 포함, 자동 retry·기한/목적 한도 reset0이다.
- 게인64/16·cap·원모델/program·물리/시간 gate·native600/motion900/
  cleanup150·headroom1380/1680은 그대로다. 회수 후 원 process/provider/
  physics consumer와 실제5041관측/421frame/완주 여부를 로컬 재검증한다.
  로컬 consumer 단회 시간이 원격 headroom 성공을 보장하지 않는다.

실물 CAN·급전·flash·모터·설치·UAC·OS 시각/시간 서비스·네트워크 설정 변경은
이 후보에도 없다. 원112 검토/소진 정본을 고정한 후 이 구체안의 새 범위와
예산·조건부 새45분에 대한 사용자 명시 결정이 필요하다.
