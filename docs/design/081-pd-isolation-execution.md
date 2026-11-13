> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 081 — 승인된 PD 관성 기준물의 실제 실행

사용자가081제안의「새45분으로계속」을명시승인했다. 관측된시작2026-10-30 03:34:44UTC(한국12:34:44)부터04:19:44UTC(13:19:44)까지전체45분이며조사/검토/영상/인계/Git저장을포함한다. 기존080계획·원장·import1/정지0/큰동작0·실패/수리이력과원제안문서/manifest는수정하지않는다.

검토된080 R2 source15를 src/simulation/pd_isolation_run/ 및outputs/isaac-pd-isolation-run-v1/로복사하고081namespace/planSHA/deadline/문서/HOST출력만바꾼다. scene/validate/reference/sdk/init_boundary/capture/torque/program/workspace의9semantic파일은080 R2와정확바이트대조한다. robot제어/원물리기준·兩독립reference의수집/독립root/실패격리수리의의미변경없음. 080의HOST215·L4R2PASS는이식원천이며081의native수용을대신하지않는다.

L급을A(이식/대조/HOST/소스검토)·B(native단계/분석/영상/인계)로분할하되전체위45분이다. L2/L4각max2, native import1/정지1/큰동작1 각600초, prepare/launch900초여유. 실패소비/원장초기화/자동새예산없음. 비작성자review079가5범주반례와9MET/UNMET·class를판정하며동일계열폴백잔여편향/외부CLI거부우회없음을보존한다. HOST215를새namespace에서재검사·source15동결후native진입한다.

fresh import→원robot2초정지+force/acceleration 관성기준물의실제PD-only/외부only/combined/coast관측→robot정지물리PASS일때같은52초큰동작을1회진행한다. reference오류는별도관측FAIL·원시prefix/journal에보존한다. 기준물PD-only의독립IΔv/dt와robot단독PD/포화/유일원인확증을분리한다. combined/robot PD미식별이면UNKNOWN이고net/cap초과를포화증거로삼지않는다. referenceFAIL도원robot정지PASS이면같은제어의동작/영상현상관측은가능하되PD분해성공을주장하지않는다. 080승인계획의기준물조건/고정허용/실패계약을그대로가리킨다.

원0.5도/1도_s·1초정착/게인64_16/cap/경로/중력조건을유지한다. 실물/CAN/보정/설치/재부팅/구매/학습없음. 질량관성가정·자기충돌OFF/바닥ON·링보류·포그invisible이다. caller폐쇄·settling15미폐쇄·provenance7/physical6/eligibility2·velocity-only가설EXHAUSTED와080의새장치미확증계보를초기화하지않는다.

실제sealed nativePNG만원속도/요약영상으로만들어full-decode·첫/중/끝확인후기존Drive날짜폴더에영상만저장·metadata재조회한다. JSON로컬. 관측실패·API실패·SDK종료·robot물리판정과영상산출상태를분리한다. 추가승인없이임계/시간/재시도조건을완화하지않는다. 실제관측/포화가미확정이면그대로표시하고한정후속후보만남긴다.
