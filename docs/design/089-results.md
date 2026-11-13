> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 089 — 실제 가져오기·2초 정지 수용 / 동역학 관측부 실패 / 큰 동작 미실행

2026-10-31 KST. 물리 장치 없는 범위로 실제 Isaac 실행을 재개했다. 실물 CAN·급전·플래시·보정·모터 운전은 NOT_RUN, hardware_approved=false다. CAD/URDF/BOM/펌웨어·제어 게인·원래 물리 기준은 바꾸지 않았다.

## 수용한 범위

- 085 원 소스16개에서 실행 경로·experiment·계획 SHA·deadline만 새089에 결속했다. 물리/관측/SDK/검증 계산12파일은 바이트 동일이며, 보호91경로와 참조11개 SHA가 일치했다. 새 HOST13그룹283개 PASS, 독립 recovery17/storage15 재실행 PASS. 비작성자 L2R1/L4R1 각각 PASS9/0이다.
- 새 import `a166bbf2af09418d855d3596ab5c289f`는 실제 child exit0·원봉인 자료/SDK 제공자·동일 입력 consumer 검증으로 IMPORT_VERIFIED. rigid bodies11 / source joints11 / runtime constraints11 / movable9, 가정 질량4.3342kg다.
- render_smoke `a28a21c91bd9433e934932338763e25f`는 실제 child exit0·동일 입력 consumer로 SMOKE_VERIFIED. 2초 정지, 실제 RTX PNG21개, 원 정착·FK·그리퍼 관계·바닥·중력 여유 기준이 통과했다. 이것은 큰 동작 수행 결과가 아니다. smoke 결과의 generic `large_motion_pass`를 큰 동작 실측으로 읽지 않는다.
- 영상은 원봉인 PNG21개를 로컬 640×480/10fps/2.1초 MP4로 인코딩했다. 전체 decode와 첫/중간/끝 PNG 시각 확인을 수행했다. `outputs/isaac-resume-089/video/provenance.json`이 원report/프레임/영상 SHA를 결속한다. Drive/Notion 전송은 하지 않았다.

## 별도로 실패한 관측과 미실행

smoke의 `dynamics_balance_status=DYNAMICS_RECORD_INVALID`, 수용 sample0을 그대로 보존한다. 원report에는 raw sample20개와 query errors0이 있지만, 실제 frozen validator 재실행에서 `Root COM world-frame finite-displacement coherence`가 거절됐다. 기준물의 NONZERO_COM_FULL6D_VERIFIED와 로봇의 15항 관측 수용은 서로 다르다.

첫 step12의 원자료를 재계산한 x/y 잔차는 각각0.0001257344 / 0.0003517859 m/s, 원허용은0.0001013112 / 0.0001035796 m/s다. 이 수치는 실제 기록의 불일치 증거이며 원인이 root 좌표계/SDK 속도 의미/solver 제약 중 무엇인지 확정한 증거는 아니다. 원값·원순서·기준을 변경하지 않았다. `balance-diagnostic.json` 및 `root-com-witness.json`을 참조한다. 새 SDK 발사는 이 진단에 쓰지 않았다.

로봇 PD/포화 UNKNOWN, moving-root 독립 교정 NOT_DONE, 질량/관성 가정, 링 보류·포그 숨김, self collision OFF/floor ON을 유지한다. 과거 큰 동작 정착15실패와 velocity-only EXHAUSTED·기타 실패/class/임계를 덮지 않는다.

큰 motion은 NOT_RUN이다. 이번 시작00:13:37Z·종료00:58:37Z, 새발사900초 여유에 따른 마감00:43:37Z를 유지했다. 정지 시험이 로컬 수용으로 완료됐을 때00:44:18Z를 확인했으므로 추가 prepare/launch를 시작하지 않았다. 시간 조건을 사후 연장하거나 과거 085의 종료 예산을 재사용하지 않았다. 원장 사용은 import1/render_smoke1/motion0이다.

## 실패 계보와 다음 지점

표준 외부 검토 bridge는 기존 Python lint로 차단됐다. 사용자 명시 선택으로 같은 계열 비작성자 검토를 수행했으며, 외부 계열 검토와 동등하다고 쓰지 않는다. 공통 편향은 잔여 위험이다. 첫 py launcher 두 시도는 Python 미발견으로 실제 script 시작 전 실패했으며, 설치 없이 발견된 기존 Python312 실행 파일을 직접 사용했다. `.dev`/전역 도구는 수정하지 않았다.

다음 시뮬 단위는 새 SDK 예산보다 먼저 이 원자료를 이용해 root transform/COM/velocity의 실제 의미와 finite-step 일관성 계약을 대조하는 것이다. 현재 원자료로 원인을 확정할 수 없으면 별도 검토된 비영 운동 기준물 범위를 제안한다. 15항을 잘라내거나 기저 가속도를0으로 채우거나 기준을 느슨하게 해 통과시키지 않는다. CAN 준비는 별도090 오프라인 보고서 단위이며 Isaac 정지 PASS를 CAN 실측으로 바꾸지 않는다.

정본 결과: `outputs/isaac-resume-089/result.json`. 비작성자 사후 자료 감사 및 최종 Git/원격 종료 대조는 이 단위의 별도 영수증을 따른다.
