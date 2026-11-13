> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 079 — 수정된 토크 계측 호출의 실제 실행

사용자는078 최초정지계측의caller NameError 수리·비작성자재검토결과와원실패보존을확인한뒤「새45분으로계속」을명시승인했다. 시작2026-10-30 02:02:49UTC→02:47:49UTC,영상·인계포함전체45분이다. 078 import1/정지1실패·motion0 원장은보존하고재설정하지않는다.

검증된078 R2 source14를새소유 src/simulation/torque_observer_run/와outputs/isaac-torque-run-v1/로복사한다. 실제계측/제어semantic변경없음: scene의 per-step observer는현재command가반환한 proof['native']에연결된다. 새driver/config의079경로·planSHA·deadline·명시예산,시험출력경로/설명만바꾼다. SDK/init/capture/program/workspace/torque.py/validate.py·모델16·힘API pin·물성가정·게인64/16·원cap·물리판정기준은078 R2와같다.

새fresh import→새2초정지계측→정지의물리및force계약통과시에같은52초큰동작·제동계측을1회진행한다. step0/prime은solver측정이아니고,양의모든step에외부명령/운동축힘/6D반력을따로기록한다. source/root의실제USD축/child/native열매핑·명령binary32/1e-8·투영내부일관성·안정clock검사를유지한다. PD단독토크/포화/유일원인을자료없이단정하지않으며UNKNOWN/INCONCLUSIVE를허용한다. 관절투영일치는독립힘교정아니다.

기존제동분석은원move후반+이어지는1초hold의오차·qd·qdd·neteffort/power·cap을사용한다. 원0.5deg/1deg_s가hold끝까지계속충족되는suffix만time_to_settle이고,미도달/끝위반/부분실행은censored다. 기준완화·정착시간늘리기·게인/cap튜닝·가속도FF변경없다. 원자료를보존하고물리FAIL을영상·분석PASS로승격하지않는다.

L급을 A(고정수리이식·HOST·검토)와 B(native단계·분석·영상·인계)로분할하고전체위45분내한정한다. L2max2/L4max2, native import1/smoke최대2/motion1 각600초, prepare/launch900초여유. **정지2회는사전선언된예비슬롯이다**: 첫실패도소비하고기계적caller/API연결결함만고정재현·L4수리검토PASS·원실패원장및sourceBsignature결속retry-proof를갖춘경우만두번째1회가능하다. force기준·물리·제어조건수리면제/완화·물리튜닝재시험에는쓰지않는다. 정상첫정지PASS면예비슬롯미사용. 새budget자동추가·원장삭제·계속발사없음.

기존HOST187+실제caller연결4를재확인한다. sourcehash로078 R2 semantic불변을대조하며원R1 NameError 재현자료는078에보존한다. 비작성자review074가AGENTS→DEV_PRINCIPLES L2/L4를수행,이전외부CLI거부우회없음·동일계열폴백잔여리스크기록. 검토는5범주반례/9MET-UNMET/클래스판정및원자료실측읽기를요구한다.

제어·CAD/URDF·SDK설치·펌웨어변경없다. 실물보정/모터/CAN/구매/재부팅/학습없음. 자기충돌OFF/바닥ON·질량관성가정·링보류·포그invisible 유지. 실제PNG의원속도/요약영상만Drive에저장·metadata재조회하고JSON은로컬보존한다. 실제계측실패/부재·SDK종료·물리정착FAIL·관측수리수용을분리해인계한다.
