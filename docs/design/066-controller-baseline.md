> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 066 — 외부 토크 PD의 영점 유지 기준 시험

사용자 진행/막힘해결·별도최신URDF지시. 제어단위09:21~10:06UTC45분, source9+plan M; L2/L4각max2, 실제감사/진단/연결 각max1(실패포함),독립SDK0. 소유 src/simulation/controller_baseline/9파일, outputs/isaac-controller-baseline-v1/,이계획. 별도067 URDF는다른agent소유이며새URDF/물성을이번제어시험에섞지않는다. .dev/CAD/BOM/047~065무수정,065frozenv2/USD·가정질량관성·링보류 유지. 재부팅/설치/실물보정/실제모터·CAN/flash/구매/학습없음.

원047 두시험은0/28 checkpoint이며solver_pd의initial_zero부터J3 -0.765594deg/qd최대약4.48deg_s로실패했다. q의FD속도와API qd의부호/크기도차이난다. 특정API/solver/FF가원인임을확정하지않고047 소진접근/열린2지적/재시도한도를보존한다.065zero-nativePD+nativeFF 영점유지2초PASS만으로047해결이라하지않는다. 새가설은 내장drive와별도FF의결합을피하고 단일총토크경로·위치FD기반D항으로 동일기준을유지하는가다. 이번에는실제관절이동전에외부PD영점유지만검증하며+5deg/56.5초/28checkpoint·RL 성공을주장하지않는다.

065source9 복사/namespace·OUT·원장·controller필드·host대조만변경. physics/providers/worker는byte-identical065. native drive kp/kd는0 유지,원cap[3,6,5,2,2,1]. full native6/12열 이름매핑과actualLINK/COM명령전1e-3Nm대조는그대로. 외부Kp/Kd는원047 solver_pd 실제 static.json의actual_drives kp/kd6값을SHA고정된입력으로읽는다(새gain/solversearch없음). 이값은그가정모델용실험파라미터이며실물/새URDF에전이승인하지않는다. source자료만읽고047실행코드/import/runtime은재사용하지않는다.

각명령은직전완성row의q와그이전row의q로native엔진시간차를사용한FD를계산한다. 첫명령의이전row는baseline0g trace마지막직전row,현재row는gravityrow0이다. 실제시각간격1/120 검증,축목표q/qd는0. P=Kp*(0-q),D=Kd*(0-FD),unclamped=nativeFF+P+D,command=원cap clamp(total). API qd는그대로관측하되D항입력으로쓰지않는다. 실제command/readback·FF/P/D/FD/APIqd/총합/포화·reference rowindex/time를actuation.control에각각보존하고 controller spec과gain-source SHA를report.controller에결속한다. API/총토크적격성오류면명령전실패한다. q/qd/state를수동으로쓰기/reset하거나원물리기준을완화하지않는다.

root는전체raw native와명령전LINK/COM검사외에controller입력SHA·정확고정gain·이전두row/엔진시간·P/D/합/포화/readback을독립재계산한다. 기존240step/241state/엔진2초·frame/FK/접촉행렬/active/float32구간·journal243record/9artifact/atomic firstfault/boundedreplace/progress no-checkpoint·실제PID/metadata/freshness/600초는보존한다. 기존check_gravity를신규check_controller로복사하되모드·닫힌controller/control schema와total토크검사만변경,기존zeroFF검사불변본보존. 체크7개hold/native_math/unsaturated/no_unwanted_contact/probe_drop/probe_settled/probe_contact_positive불변,hold기준q<=.5deg/APIqd<=1deg_s에추가FD속도<=1deg_s도요구한다. APIqd↔FD차이는별도관측통계이며원인을단정하지않는다. 유효동역학FAIL/local1과증거오류FAILED/nonzero를분리한다.

원065원장SHA7e8b2b2865c9b5ae192222fc5211334dae6a8f37a8ddcc24a3da7f3ee1355b85/schema1/legacy_064/정확3목적IDs149212745c084e77b6d8f4a0d3686b31,7999bab305da4750a94774eb12752352,4ab4c7d5cb6a4e2ba1c862070e30a1a8을고정하고새legacy_065에nested보존한다. 원065delivery/원047static gain reference 실제SHA를settings에추가한다. 새source입력으로audit→진단→연결 각1회. 구065prepared/실행은그대로두고재예약하지않는다. 완료정리가능한단계만10:06cap내착수한다.

host는기존34대조를보존하며모드/controller/control이필요한fixture만갱신한다. 외부PD수학비영점/FD시간차/축순열/총합포화검사,APIqd만변조시D항불변대조,과거q/FD/P/D/합/게인·inputSHA/명령변조를journal/checkpoint/report함께재봉인해독립root거절대조한다. 정상/증거FAIL/유효동역학FAIL·초기예외/cleanup/잠금/progress권한대조를유지한다. AST·3불변파일·기존frame/contact함수비교·범위whitespace/host 후L4,source동결후실제3단계. 원자료/출처/종료코드/모듈·clock·metrics/6PID·Kit·lock·원065SHA불변·manifest/HANDOFF를보존하고소유scope만commit,push없음.

기존provenance7/physical6EXHAUSTED·eligibility2next동종독립실측+작성자수용1충분임계/firstfault·CC062/CJ064/SR065정적폐쇄·063overwrite소스소진·047의BLOCK_EXHAUSTED를유지한다. 새영점제어가설은047같은solver/PD gain재시도나28checkpoint기각이아니다. 비작성자class착지·소진처분요구,외부hook재시도없고samefamilyfallback잔여. 067새URDF에는이번물리시험PASS를상속하지않는다.
