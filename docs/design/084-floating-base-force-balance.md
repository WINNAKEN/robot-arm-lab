> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 084 — 승인된 15항 동역학·저장 경계 수리와 변경 사양 대조

사용자는 새45분 실행·기준무완화·실물제외·영상, Mech-Sparring의 모터 변경 검토와 통신모듈 도착 전 준비를 승인했다. 첫 시계07:46:03UTC(한국16:46:03)부터08:31:03UTC까지 검토/실행/영상/인계/커밋을 포함한다. 새 prepare/launch는900초 여유, 마지막08:16:03UTC 이전이다. L2/L4 각최대2, native import1/render_smoke1/motion1·각600초, 자동재시도/자동새예산 없음.

소유는 src/simulation/floating_balance_trial/ 및 outputs/isaac-floating-balance-v1/, 본계획·084결과·변경사양/통신준비 문서와 최소인계다. 083 source16/원실패/원장/영상과 CAD/URDF/다른 프로젝트/펌웨어를 변경하지 않는다. robot 제어/경로/게인64·16/cap/원정착0.5도·1도초·1초/속도/중력/바닥/FK/그리퍼/영상 기준은 그대로다. 질량관성 가정·자기충돌OFF/바닥ON·링보류·포그숨김을 유지한다. 모터 변경은 현 가정과의 차이로 기록하며 확인되지 않은 사양으로 질량/토크를 올려 현재 실패를 통과시키지 않는다.

## 저장 경계

Boundary는 전체 pre/post 자료를 native-steps.ndjson에 같은 순서로 보존하되 JSON audit에는 bounded 초기 이벤트와 원journal SHA/건수/양의pre/post 건수만 담는다. root는 원journal 전체의 시간·q/qd·순서·step 수를 기존 허용 그대로 검사하고 SHA/건수도 대조한다. 긍정 이벤트를 생략하거나 요약만으로 수용하지 않는다. 마지막 init audit 및 report가 동일한 거대 이벤트 배열을 반복 직렬화하지 않게 한다. fault는 전체 journal에 남기고 요약오류 목록은 유한하게 제한한다. 정상/예외/이중저장실패/큰6240step HOST 대조로 크기·참조수명·순서를 확인한다.

native 시간초과/실패 시 부모는 REAPED 후 별도 recovery-manifest.json을 만든다. 상태 FAILED·원job/hash·exit·원파일 해시·재실행없음을 표시하고 native terminal/report와 구분한다. 정상 실행의 terminal 계약은 그대로며 실패 manifest로 성공 판정하지 않는다. 쓰기 실패도 명시하고 nonzero를 보존한다. 과거 누락파일은 소급 생성하지 않는다. 600초를 늘리지 않는다.

## 15항 관측

같은 원step pre/post에서 실제 shared_metatype.fixed_base·DOF/링크 이름·M/C/G 전체형상과 원Tensor root transform·세계COM 선/각속도를 읽는다. root가 canonical Base인지, 동일 clock의 root/link0 transform 및 속도와 일치하는지 검사한다. COM offset/회전도 readback으로 결속한다. 15×15는 실제 floating flag와6+9 순서가 맞을 때만 처리하고9×9는 fixed flag일 때만 처리한다. 15항 전체 평균가속도로 Mpre*qdd+Cpre+Gpre를 계산해 모든 root-관절 교차항을 보존한다. 기저0대체·행렬절단·다른step 혼합은 금지한다. G 전체는 같은 기존 명령의 원 full query와 결속한다. 관절9개 성분만 결과로 표시할 때도 계산은 전체15항이다.

독립 HOST의 알려진 결합행렬·비영 기저가속도·순서/좌표/COM/clock 반례로 식을 확인한다. 실제 API 문서와 actual cross-read를 대조하되 정지한 기저가 좌표원점을 실증 교정했다고 주장하지 않는다. native 비영COM 기준물 full6D는 계속 별도로 검증한다. 로봇15항 계산은 단계평균 유한차분 추정이며 기저 프레임의 독립 운동 교정이 남으면 PROVISIONAL로 표시한다. 구속/감쇠/외부기여 미분리 상태에서는 robot PD/포화/유일원인 UNKNOWN을 유지한다. 기준을 사후fit하지 않는다.

## 순서·자료 검토·전달

L2 통과→083 동결복제/수리→HOST/동결→비작성자 L4 PASS→fresh import→2초 정지→원물리정지PASS일 때52초 큰동작. 관측오류/미지원은 독립 상태로 보존한다. 목적별1회 후 추가 SDK 없음. 실제 봉인 영상 또는 실패 시 회수해시/프레임별 검증된 진단 영상을 구분해 기존 Drive 폴더에 영상만 저장·metadata 재조회한다. JSON 로컬, decode·첫/중/끝 확인.

모터/BOM/설계 자료와 관련 생산 대화는 읽기만 하고 변경사양 표를 새 문서로 저장한다. 현재 모델의 모터·질량·토크 가정과 NEMA23 등 큰모터 후보/확정 여부를 대조한다. 사용자 최신 사실: J2/J3용40mm NEMA17두개 준비, CAN통신모듈 미도착·다음주 예상. 두축 시험과 최종6축 모터선정은 분리한다. 통신준비는 기존 firmware/배선/codec/HOST 자료를 대조해 핀·프로토콜·도착후확인·장치비활성 절차를 정리하며 플래시/실물CAN/보정/모터운전/구매는 하지 않는다. 조사한 원자료·미확정값·가정의 SHA와 출처를 남긴다.

검토자는 API/SSOT/오류/순서/범위5범주,9MET/UNMET 및 class를 실제source/caller/HOST로 판정한다. 동일계열 폴백 편향을 기록한다. 기존 정착15실패·provenance7/physical6/eligibility2·velocity-only EXHAUSTED 및 성공범위를 보존하며 새도메인소진을 작성자가 선언하지 않는다.
