> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 081 제안 — 수정된 PD 기준물의 실제 실행

상태: 사용자 새 실행 예산 승인 대기, source/SDK 미실행. 080은M45(2026-10-30 02:48:15~03:33:15UTC)이며 prepare/launch900초 여유가 고정돼03:18:15UTC 이후 새 native 발사를 하지 않는다. 080의연결/기록/의미조건3결함수리·HOST215·비작성자L4R2소스PASS를보존하며원예산을조용히늘리거나원장을초기화하지않는다.

승인되면그시각부터새45분인별도실행단위를연다. 080 R2 source15를 src/simulation/pd_isolation_run/ 및outputs/isaac-pd-isolation-run-v1/로이식하고081원장/planSHA/deadline/문서·HOST출력namespace만바꾼다. reference/robot제어/검증코드의의미변경없이SHA대조한다. 기존원장/실패계보/검토상한소진이력은보존하며새단위L2/L4max2·native import1/정지1/동작1 각600초·시작900초여유다. source동결·HOST·비작성자검토후실행한다.

fresh import→2초robot정지+두독립관성기준물의실제PD-only/외부only/combined/acceleration/coast 관측→원robot정지물리PASS이면동일52초큰동작과영상. reference오류는별도관측FAIL로보존하고PD분해PASS로승격하지않는다. combined/robot의단독PD·포화는식별불충분이면UNKNOWN이다. 기준·게인64_16·cap·경로·물성가정·自己충돌OFF/바닥ON·링보류·포그숨김은같다. 실물/CAN/보정/설치/재부팅/구매/학습없음.

실제native PNG원속도/요약영상만기존Drive날짜폴더에저장하고크기/MIME/부모재조회,JSON로컬·원자료/인계/manifest저장까지새45분에포함한다. 관측성공과정착수용·단독PD/포화식별성공은각각분리해보고한다.
