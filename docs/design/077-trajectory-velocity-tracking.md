> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 077 — 위치 경로와 속도 목표 일치

사용자 지시: 큰 이동 뒤 궤적 추종·정착을 새 계획으로 수정하고 기준을 완화하지 않은 재검증과 영상을 남긴다. 실물 운전 제외. 076 원본 실패·원장·물성 가정·링 보류를 보존한다.

현재 source 관측: quintic 위치 목표를 매120Hz 갱신하지만 tensor velocity target은9축 모두0이다. 이것이 미통과 정착의 원인인지는 아직 추론이다. 원076 기록을 읽어 이동 중 목표 속도 불일치·추종 오차·중력 차감 후 cap 여유를 수치화한다. 실제 구동 토크를 기록하지 않았으므로 cap 포화를 실측했다고 주장하지 않는다.

변경 후보는 한 가지: 같은52초 quintic 경로의 해석적 도함수 dq/dt = delta*30*u²*(1-u)²/T 를 velocity target에 전달한다. hold·경계·고정40mm 그리퍼는0이다. Kp64/Kd16·gain backend·중력FF·원cap·관절속도·정착0.5deg/1deg/s·바닥5mm·가져오기/정지/큰 동작 게이트·시간코덱·포그invisible는 유지한다. 가속도 FF·게인 튜닝·시간 늘리기·오차 기준 변경은 하지 않는다.

명령은float32 tensor API에 맞춰명시적으로IEEE754 binary32로인코딩한다. source의해석적reference_velocity와encoded velocity_targets를같이기록한다. root는독립적인phase/미분계산과struct binary32왕복으로예상명령을재계산하고원velocity readback1e-8기준을유지한다. 입력참조와실제readback양쪽을검사하며관측값반올림으로실패를지우지않는다. 소스명령의9DOF순서·유한값·원속도한계를검사한다. 목표position·정착측정의targets는기존기구학경로를그대로사용한다.

소유: src/simulation/trajectory_tracking_trial/는076의13파일복사본이다. 실제변경은scene.py/validate.py/시험과별도experiment·plan·deadline·경로이며sdk.py/init_boundary.py/capture.py/program.json/workspace.py·모델16파일은동일하다. 결과는outputs/isaac-trajectory-tracking-v1/. CAD/URDF/펌웨어/공유규율/설치SDK는수정하지않는다.

L급을유한두단위로분할한다. 전체새예산45분시작2026-10-30 00:17:50UTC→01:02:50UTC,인계까지포함하며상한소급변경없음. A=자료진단·구현·HOST·L2/L4(목표00:35:50전),B=검토된동일소스fresh import→2초정지→52초큰동작1회·영상·인계. Native각목적max1·각600초,900초미만남으면새nativeprepare/launch금지해회수·root·영상·인계시간을남긴다. L2max2/L4max2,실패소비·서로다른실행부분PASS합성금지. 새로운튜닝분기/별도계획/자동추가예산없음. 최초큰동작이물리FAIL이면원본과영상·원인후보를보존하고새재시험하지않는다.

HOST: 기존48/29/초기화14/정리15/정규화13/코덱13 + 새미분/경계/finite difference/float32/9DOF순서/속도readback음성검사. zero velocity로되돌리기·도함수부호반전·phase한스텝틀림·관절열교환·제한초과·NaN/inf를거부한다. 기존076record의zero velocity는새계약에서거부하며nativePASS로승격하지않는다. source와root상호호출없는독립식으로검사한다.

AGENTS→DEV_PRINCIPLES의L2/L4역할분리에따라비작성자review074를재사용한다. 이전외부계열검토호출의승인거부를우회/재시도하지않고동일계열별도세션폴백의잔여편향리스크를기록한다. 작성자는최종검수자가아니다. 검수는호출/API·상태/SSOT·오류·순서·규율각범주에구체반례또는해당없음근거,원076의미폐쇄물리문제·새class재발/소진여부를요구한다.

영상은실제nativePNG만사용하며전체/요약MP4와실패여부를보존한다. Drive에는영상만저장하고크기/MIME/부모를재조회한다. 별도provenance JSON은로컬보존한다. 모델자기충돌OFF/바닥충돌ON·물성가정은한계로명시한다. 재부팅·실물보정·모터/CAN·설치·구매·학습없음.
