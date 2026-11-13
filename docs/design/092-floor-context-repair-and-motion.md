> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 092 — 091의 import/scene 검증 문맥 연결 수리·요청된 큰 동작 계속

2026-10-31 KST. 현재 사용자의 COM원인파악·수정·큰동작까지 요청을완료하기위한코딩/실행분할단위다. 091 원장 import1/smoke1 실패·motion0은그대로종결하고자동동일SDK재시도를하지않는다. 새092는실측으로확정된검증연결부수리후남은큰동작목적을수행한다. 사용자에게새45분명시승인을받았다고쓰지않고기존명시작업범위에M/검수급단위상한을적용한다. 첫분할시계02:38:00Z, 종료03:23:00Z(한국12:23), 새발사03:08:00Z마감·900초여유·native600초·목적별import/smoke/motion각1회다. 변경없는코드를반복발사하지않는다.

검토계보는091부터이어진다. 전체L2 max2 중이번R2, L4 max3 중수리R2와사후R3를사용한다. 새폴더라고반례/class/소진·라운드원장을초기화하지않는다. 이수리후추가예산을자동생성하지않는다. 실물CAN/급전/flash/보정/모터/설치/구매/재부팅/전원정책/학습은없고승인false를유지한다.

## 확인된 실패와 범위

091 smoke `88670c028b6a4cb8b63a6db3d0e15f0e`의원terminal은`ValueError: all source colliders including floor`, failure.txt는scene415→verify_import→check_colliders(default floor=False)다. 새BaseBefore는이미floor포함12 collider인데import검사는원래11 collider전용이었다. 161.532초/child1/REAPED/timeoutfalse, native긍정step0이며RootAPI이동전실패했다. generic consumer FAILED의sdk_connected:false를SDK미시작으로읽지않는다. 원인ROOT가설은아직실제수정검증전이다.

## 최소수리와 새결속

소유는새 `src/simulation/fixed_base_motion_run/`, `outputs/isaac-fixed-base-092/`, 본계획/결과·091원인조사추가/최소인계다. frozen091의17파일을복제하며091source/원모든실패파일은수정하지않는다. driver/output/experiment/remote root/planSHA·config deadline·README/test_scene출력만092로결속한다. SDK lifecycle/제어/렌더/Physics program/게인·cap·물성·URDF/형상·바닥/정착원기준은같다.

- `verify_import(model,packet,cfg,*,floor=False)`로선택문맥을명시한다. 기존진짜import호출은false그대로여서11개를강제한다. 이번before-scene호출만`floor=True`로12개를강제하고경로/형상/설정/세계좌표를원check_colliders가모두검증한다. 바닥을필터로빼거나필드누락을허용하지않는다.
- HOST에실제089 static-smoke/floor포함packet을이용해기존false문맥의실패를재현한다. 수정후true문맥양성, floor삭제·중복·disabled·badcorner/path·false문맥으로scene오입력·true문맥으로floor없는import입력의음성검사를실행한다. 기존310과root/floating양쪽원검사를유지한다.
- 분리된before/afterroot USD/actualfixedtrue/완전한M9,C9,G9/양쪽COM원시검증·모든원관측과fixed-root 강한smokegate는091검토코드그대로다. 원floor-context에만수리를한것이지COM원허용을완화하는것이아니다. frozen최종소스를비작성자L4R2로검토한뒤fresh import→정지2초→fixed9/COM/원정착통과때만52초큰동작각1회다.
- rawUID/job/plan/common/driver/source해시를새원장과결속하고과거proof를새증거로다시표시하지않는다. 원시SDK자료와실제PNG만으로영상/결과를남긴다. 첫/중/끝·전체decode, 프로세스/lock해제·보호파일불변·인계·로컬commit을끝낸다. 외부업로드없음.

## 판정

091RootAPI가설은092실제fixedflag와COM/9항API가검증될때까지확정하지않는다. 수정성공도기존floating15나moving-root교정을완료했다는뜻이아니다. 큰동작을실행해정착이실패하면그사실과원실행을보존하며게인/캡튜닝·사후fit·재시도하지않는다. 기존큰동작정착15실패와velocity-only EXHAUSTED·모든임계를유지한다. 동일계열비작성자폴백은사용자승인이지속하며공통편향을명시한다.
