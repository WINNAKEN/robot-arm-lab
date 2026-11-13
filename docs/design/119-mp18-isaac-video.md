> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 119 — MP18 URDF v4 Isaac 검증·영상·Drive 전달

2026-11-07 KST. 사용자 「진행하고 영상까지 남겨서 드라이브에 올려」는 직전 제안(로컬 준비/검토→v4 가져오기→정지→통과 시 작은 동작→큰 동작)의 실행과 영상 업로드 권한이다. 별도 일반 실행 승인을 반복하지 않는다. 실물 CAN/RS485, 포트/전원/flash, 설치/구매, 네트워크/시계 설정, 기존 CAD/URDF/116/118 수정은 없다.

## 입력·승인 경계

정본 v4는 118 freeze-r2의 model74파일/URDF d55f0cbd…/질량8.863854736164349kg이다. 정본과기존자료를보존하고 `src/simulation/mp18_isaac_119/`, `outputs/mp18-isaac-119/`, 이계획과최소추가인계만쓴다. SDK는기존 isaacpc/C:/isaacsim 6.2.0-rc.14,기존IsaacLab/prefix/수치provider를그대로사용한다. SDK bootstrap/observer/init-boundary/capture/winjob은실제로성공한108/116의읽기전용핀을재사용하되 v3전용 모델16파일가정/검증/실행승인을새모델에이식하지않는다.

새모델의표시자세중력모멘트(원장질량/URDF FK,kg·m·9.81로직접계산)는J2 9.418032982Nm/J3 5.235242891Nm이며원본임시cap6/5Nm를넘는다. 원cap유지지시가있어질문중이다. 선택1은이번시뮬에만 J2 12/J3 7Nm override,선택2는원cap으로가져오기·정지진단만한다. 게인64/16·속도한도·정지0.5deg/1deg/s는고정한다. 원본URDF를고치지않고runtimeoverride의원값/새값/사용자답변을기록한다. cap변경답변없이이를시행하지않는다. import/로컬준비는답변과독립해진행가능하다.

## 분할·검토·예산

L1→비작성자다관점L2(논리만)→L3→기계HOST→비작성자L4(전체),L2/L4각max2/noR3·결함합집합. standard Sonnet bridge는이번에도기존절대경로Python lint로차단됐다. 도구수정/우회없이기승인동일계열비작성자2렌즈폴백을사용하며외부계열부재/공통편향을명시한다. 기존실패·소진원장을삭제/리셋/재분류하지않으며119의다중visual/fulltensor/v4기하·원격owner경계는새source로구분한다.

* A 계약/경로/프로그램: contract.py, config.json, program.json, test_contract.py 최대4source/S1500초(검증예비150). root 소유. 모델/출처/외부SDK핀,전체74파일,의미있는변조음성,profile/FK/중력/바닥대조를담는다.
* B native: native.py와test_native.py 최대2/S1500초(예비150). 별도Codex작성자소유. importer/runtime/readback/단계gate/캡/카메라를담는다. SDK부재HOST와실제native결과를분리한다.
* C 원격owner: driver.py와test_driver.py 최대2/S1500초(예비150). root 소유. 실제실행소스/모델봉인,폐쇄목적/경로/한도,Windows Job에의한local SSH와remote SDK child생명주기/회수/검증을담는다.
* D 영상/전달: media.py와README 최대2/S1500초(예비150). root 소유. frame 원시자료→MP4/ffprobe/시각검사/Drive제한파일전달. source수는파생JSON/PNG/ZIP과구분한다.

각첫작성부터누적,수정도원예산을소비한다. 동결SHA·시작/끝을기록한review/의존대기만분리한다. L2/L4 각렌즈M2700초/회이다. SSH/SDK는소스검토후에만시작한다. 첫원격명령부터전체2700초단일시도,SDK child1개/retry0이며같은프로세스에서단계별gate를통과한다. import/startup<=600초·정지<=300·작은동작<=300·큰동작<=900,SDK전체<=1800초·cleanup2초,같은실행의archive/fetch/검증예비를남긴다. 부족한headroom에서는다음단계를시작하지않는다. 전역시간은local monotonic이며아래bounded handshake로remote기한을보수결속해NTP를요구하지않는다. Drive업로드는닫힌원격실행이회수된뒤의로컬전달이다.

R2 원격기간 번역: local payload준비뒤 교환시작 t0에서 global 잔여 L을 고정한다. remote bootstrap은 SDK/디렉터리작성을시작하지 않은 채 READY(nonce/run/source-hash/remote monotonic r0)를 보내고, 자신의 r0+20초 hard fence 안에서 같은 identity의 단일 GO만 받는다. local은 READY를 t0+20초 안에 수신·검증했을 때만 GO를 쓰며, 늦은 READY/EOF/불일치/late GO에는 SDK예약이 없다. remote 전체 lease는 `r0+L-20`이다. READY의실제생성이t0..t0+20안이므로 remote lease의실제만료는localglobal기한을넘지않는다. GO뒤의payload수신/새119run생성/SDK Job·감독·같은run의zip작성도이lease안에서끝내며 SDK에최대1800초를주고cleanup/zip/fetch예비를차감한다. local SSH Job의전체work기한과그stdin sender의20초handshake기한은별개로강제한다. local SSH 종료를remote SDK종료증거로쓰지않고 remote Job의actual PID/exit/reaped/active0를회수한다. 원격command가큐에서늦게시작돼도GO가없어닫히며, archive command를늦게새duration으로재무장하지않는다. HOST는queue/late READY/late GO/EOF/nonce변조/남은시간부족과경계값을시험한다. R1 duration단순전달 지적/원문은보존한다.

단일SSH 스트림에서 GO JSON+봉인ZIP을stdin으로보내고READY/결과ZIP의길이·SHA header와원래바이너리를stdout으로받는방식으로staging과회수를같은lease에넣는다. SDK stdout/stderr는remote Job의별도파일로보존해RPC스트림과섞지않는다. bootstrap은20초admission fence를먼저걸고GO뒤동일감시자를globallease로전환하며(무감시구간없음),payload를검증한뒤immutablewinjob으로SDKchild를소유한다. root는처음준비한bundle/sourcehash,nonce,runid만인정하고다른run조회나기존인스턴스종료를하지않는다. 스트림·archive검증이실패하면현재실행의실패를보존하고 SDK재시작은없다.

## 실제 흐름

1. 원본74파일/추정물성/11physical+tool0/9DOF/7독립좌표/47색visual/11compoundcollision을새계약에핀한다. geometry단위/프레임과full inertia를별도검사한다. 현행URDF 범위를쓰고미확정물성·57D단자가정을공개한다.
2. 로컬에서최종선택profile의120Hz 표본을전수확인한다. source FK와상태별전체링크경계를이용해책상z0과관절한도/속도를검사한다. 큰동작은J1yaw/6축이동을포함하되통과한v4경로만사용한다. 게인/속도/기준은유지하며거짓충돌을숨기는모델편집은없다. selfcollision은이전진단과같이disabled로기록하고,selfcontact안전수용주장을하지않는다. collision mesh의source기하와실제native approximation설정을대조하고그차이를기록한다.
3. user답변·localHOST·최종L4수용·원본보존을봉인한뒤,119전용remoteUUID폴더에만봉인payload를옮긴다. runtime소스/데이터/설치핀을새로확인하고closedentrypoint만실행한다. 기존SDK만사용하며새패키지를설치하지않는다.
4. 실제URDF importer로USD를만든다(mergefixed=false,mergeMesh=false,fixbase=true,collisionfromvisual=false). 모든색visual·물성fulltensor·관절axis/origin/limit·툴프레임·실제fixedbase를readback한다. importer가tool0를물리body로만든경우기존과같이sole tool0_mount/body API만명시정규화하고전후원자료를남긴다. 그리퍼mimic은실제schema/DOF상태를기록하며command coupling과기어접촉물리를구분한다.
5. 기존핀SDK provider로CPU PhysX/Lab를초기화한다. zero-time 초기화관측/경계(기존init_boundary)를지켜초기q/qd가움직이지않음을확인한다. 실제11링크질량/COM/full inertia와source를대조한다. Native gravity compensation은현재worldCOM의독립virtual-work합과맞추고,총FF+drive가승인된runtimecap을넘지않게남은drivecap을기록한다.
6. gravity-on 2초정지: 모든arm오차<=0.5deg,속도<=1deg/s,base/clock/모델상태/finiteness/desk조건을통과해야작은동작으로간다. 작은동작은느린최대5deg수준,통과한뒤최대42초큰동작을한번만한다. 큰동작34초정착판정도원0.5deg/1deg/s로유지한다. 출력큰모션은로컬한도/바닥/중력cap검사를통과한최종프로그램에결속한다. 실패시즉시이후동작을NOT_RUN으로남기고기록가능한실제진단영상은보존한다. 숨은retry/자동게인·cap확대는없다.
7. 실제RGB를640x480/10fps로수집하고physics clock과frame fresh generation을연결한다. render가physics를추가진행시키지않음을확인한다. 초기/정지/작은/큰각단계의frame기록과JSONL을flush하며실패해도이미기록한영상자료를회수한다. 장치가없는HOST모형/뷰어그림을Isaac실행영상으로대체하지않는다.
8. 앱close와실제child exit/Job active0/reaped를확인하고같은run결과만회수한다. 실패시도복구를위해새SDK를실행하지않는다. 로컬소비자가source/run/PID/hash/진단통과/단계순서/frame시각을검사한후MP4를만들고,ffprobe의크기/fps/길이/frame수와처음/중간/끝실제화면을확인한다. 정지또는단계실패는영상/결과에그대로표시한다.
9. Google Drive 연결도구로닫힌MP4와개인정보를제외한짧은결과파일만새로올린다. 동일이름robot-arm-lab 폴더가여러백업경로에있어기존폴더를임의선택하지않고MyDrive의새전용 `robot-arm-lab-Isaac-v4-119` 폴더를사용한다. 공유권한은바꾸지않는다. 업로드응답과Drive metadata readback으로파일명/크기/폴더를확인하고관측된URL만전달한다. 원시SSH로그·키·설치정보·전체저장소는업로드하지않는다.

## 수용

localsource수용,actualimport수용,gravity정지수용,작은/큰동작수용,실물성능,Drive전달을별개로판정한다. v3/116의수용·실패를v4로소급하지않는다. 최종인계에는각단계PASS/FAIL/NOT_RUN,실제영상/Drive링크,예산/실패이력,추정물성/selfcollision한계,모델과기존자료보존,실물통신0을남기고119소유자료만선별로컬커밋한다.
