> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 097 결과 — 고정 목표 정착 진단 후보

2026-11-01 KST. 상태 **OFFLINE_REVIEWED_PROPOSAL_COMPLETE_NATIVE_NOT_RUN**. 다음 진단을 위한 별도42초프로그램후보와HOST검증을완료했다. src/CAD/URDF/BOM/펌웨어·기존095/096은무수정, 새native/SimulationApp/SDK/SSH/네트워크/실물CAN/급전/모터/flash/설치/보정/학습/외부업로드0, hardware_approved=false. 새45분시계도만들지않았다.

후보는원첫9segment/0~34초를그대로두고,34~42초고정목표8초를붙인다. 33~42초전체9자유도목표와명령속도0을유지한다. 원52초전체경로의완주시험과다른진단이다. 게인64/16·cap·원물성·위치0.5°/속도1°/s등원수용기준을바꾸지않았다.

실제기존scene.target_at/validate_program/checkpoint와validate.pmodel을SDK없이호출해원명령prefix4081표본완전동일,고정목표hold1081표본,42초/5040step/5041관측/421capture,checkpoint2/8/15/25/34/42초를검증했다. 이수량은실행계획/명령검증이며새물리표본이나PNG가아니다. 원095봉인report의실제34초행을기존checkpoint에재생해J3/J5실패를보존했고,별도42초합성성공을함께두어도합성결합결과는실패다. 실제42초관측은NOT_RUN이다.

HOST30은prefix/hold타축/게인/기준/중력/opening/카메라/수량/checkpoint변조및bool/중복/비유한JSON거절과정상양성·원실패보존을검증했다. 재현경로는 outputs/isaac-hold-proposal-097/README.md·verify.py·test_host.py,자료는program.json/verification.json/host.json/host-final.json이다. 기존보호4482+096증거/소스/ignoredZIP등총5773파일의불변을검사한다.

L2 R1 BLOCK7/2·지적3(F1 URDF reader소유,F2 wrapper150초/정리예산누락,F3 실제childspawn입장시각)을수용하고원계획을보존했다. R2 PASS9/0,세지적은계획논리범위에서폐쇄했으며098실행기구현/실경계HOST는아직남았다. L2 R2 brief/JSON에손전사한해시65자오기를첫후보생성게이트가거절했다. 실제계획바이트는변경없고,원결과/최초실패를보존한별도비작성자해시정정기록으로같은검토대상을확인했다. 새논리검토나R3는없으며L2 2/2종결이다. 동일계열공통편향을유지한다.

후속098 제안은수정회수경로와이후보를새runner/freeze에통합하고L2/L4각max2·HOST를마친뒤**첫원격명령직전부터새45분**을쓰는것이다. import1/정지1/motion1,정지수용선행,추가SDK/자동retry0. watchdog600/600/900,transport여유150,회수각300/총600,정리30을포함해실제spawn직전남은여유1380/1680초를검사한다. 최악4440초로45분내세목적보장없음,늦으면motion미실행이다. 이runner는미구현이고현재후보는native-ready가아니다.

42초에서통과하더라도원34초실패/전체consumer결과는유지하며관측창진입만별도로보고한다. 긴hold가해결한다는결론은없다. 유일원인·실제PD토크/포화UNKNOWN,moving-root미교정,물성가정·링보류·포그숨김·자기충돌OFF/바닥ON,정착15·velocity-onlyEXHAUSTED와과거임계를보존한다. 실제수리원격성능/정착/전체physics는NOT_RUN/PENDING_USER_SCOPE_AND_BUDGET다.

L4 판정과최종기록은검토후이아래에한정해추가한다.


## 최종 검토와 기록

L4 R1 **PASS9/0**. 작성자 HOST30과 별도 비작성자 HOST30을 통과했다. 비작성자는 실제 소비 경로·잘못된65자 해시 거절·기계검사 메타데이터 음성3개·보호5773파일/목록·22텍스트 공백0을 독립 확인했다. 새지적0/미해결0이며 097 범위 NOT_EXHAUSTED, L2 2/2·L4 1/2로 종결한다. 추가 자동검토/실행은 없다. 동일계열 공통편향과 후속098 구현·실행 미도달은 유지한다. 정본은 outputs/isaac-hold-proposal-097/review/L4-r1.json이며, 검토 뒤 변경은 이 상태/판정 데이터·result·원문 보존 인계·index 영수증·로컬 커밋에 한정한다.
