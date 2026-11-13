> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 115 — 닫힌42초 자료의 참조 입력·정착 응답 분리

2026-11-06 KST. 사용자 「계속 진행해」로114에서 남은 J3/J5 정착 문제의 오프라인 분석과 구체 후속안을 진행한다. 114 원격 단일시도는 이미 소비했다. 이번115는 새 SSH/SDK/native/시계·네트워크 변경/실물 CAN·RS485·급전·flash·모터/설치/구매를 실행하지 않는다. 게인64/16·cap·모델·기준0.5°/1°/s·34초 판정과 원114 결과를 보존한다. 완료된114의 남은 시간을 재사용하지 않는다.

## 소유·유한 절차

소유: 본 계획, outputs/settling-reference-analysis-115/의 분석기 analyze.py·의미 회귀 test_analyze.py·생성 자료, _research/115-settling-reference-analysis.md, 최소 .dev/HANDOFF.md prepend·SESSION_HANDOFF.md append. 기존 src/전체·모델/CAD/BOM/펌웨어·114 증거는 읽기만 한다. 새 운영 실행기·새URDF·새물리 consumer는 만들지 않는다. 현재 foreign CODING_RULES WIP와 MP 작업을 보존한다.

단일 S 분석 단위(분석기·회귀·연구서·계획): 첫 분석기 write부터 구현/HOST/수리/root 검증 누적1500초, 독립 검토 동결 대기는 별도, reset0. L2/L4 각각 최대2회·검수급2700초·noR3. 리뷰어는 기존 비작성자 한 명을 재사용한다. AGENTS→CLAUDE→DEV_PRINCIPLES의 생성/평가 분리와 topology-roster 슬롯을 따른다. 막힌 Sonnet bridge 재실행/수리는 하지 않고 사용자가 기승인한 동일계열 비작성자 폴백·공통편향을 명시한다. 외부계열 가용 시 전제 재검증을 우선한다. plan L2 뒤 실제 분석기 작성, 기계 검산 뒤 L4를 진행한다. 추가 일반 확인 없이 이 오프라인 범위를 완료한다.

## 고정 입력·측정

114 source-freeze945f77d9…·receipt06580f4f…·native ZIP7ee08b1d…·report08fecbc9…·원 scene/workspace/consumer/program·원114source10과 보호69/CAD22/critical112/113을 SHA256으로 고정한다. 실제 report5041행과 motion.ndjson의 투영(q/qd/targets/속도명령/phase/time/step/남은cap)을 전건 대조해 사용한다. report와저널의 중복 관측은 독립물리실험으로 세지 않는다. 새 결과는 별도 exclusive 파일로 쓰며 실패를 원본에 덮지 않는다.

1. 원 scene.target_at의 실제 순수 경로를 SDK 호출 없이 5041시점에서 실행해 원 targets·reference_velocity·binary32 velocity_targets·phase·gravity를 대조한다. 별도 수식의 quintic 위치/속도/가속도·좌우 경계도 대조한다. endpoint 위치/속도/가속도 연속성과 jerk 점프를 구분한다. 숫자양성과 NaN/중복/연속행누락/target변조/phase변조의 거절을 시험한다.
2. 6 checkpoint를 원 scene.checkpoint로 재계산한다. 34초 J3/J5 실패·42초 통과·원 전체실패를 확인한다. 같은 목표33~42초에 한해 각축의 오차·속도·peak/zero crossing·최초이후지속통과를 계산한다. 다른 목표 구간을 섞지 않는다. 모든9축과J3/J5개별을 분리하고 원endpoint 판정과 사후 연속범위를 분리한다.
3. 이동 종료 전 마지막1초와 뒤 고정목표9초의 J3/J5 및 다른축 응답을 비교한다. 원 source cap에서 FF를 뺀 budget·실제 설정값의 일치를 확인한다. 이것은 명령 cap이며 PD 포화의 직접 관측이 아니다. native projected net effort·balance estimate도 isolated PD sensor로 부르지 않는다.
4. hold의 연속 표본에서만 부호 peak 시간·감쇠·주기를 계산한다. 충분한 peak가 없으면 UNKNOWN이다. 선택적으로 AR(2)+상수 경험모델을33~37.5초 training/37.5~42초 holdout에 맞추고 실제 오차/속도 대비 검산한다. holdout은 같은실행의 시간분할이며 독립native검증이 아니다. fit이 불안정/특이하면 reject하고 인과·다축분리·실물예측으로 사용하지 않는다. 모델 적합만으로 원인이나 수리를 확정하지 않는다.
5. 원 quintic와 endpoint jerk0의 septic(35u4−84u5+70u6−20u7)를 수식 수준에서 비교할 수 있다. 같은8초/같은endpoint/원34초 및42초 deadline·gain/cap을 유지한다. 실제9축 전체표본의 위치·속도 한계와 기존workspace static geometry/gravity를 확인할 때만 별도 비활성 후보를 남긴다. 후보가 더 빠른 peak속도/가속도 등 tradeoff를 숨기지 않는다. 단순히 더 부드럽다는 이유로 정착개선/물리PASS를 예측하지 않는다. 실행 scene/consumer는quintic전용임을 명시하고 후보JSON을 바로실행가능하다고 표시하지 않는다.

## 한계·후속을 구체화하는 기준

오프라인 자료로 결론 가능한 것은 원 참조 신호의 오류 유무, 같은 목표의 잔류진동, 경험적 주기/감쇠, 설정 cap/원 numerical·정착 판정이다. 결합모드/특정 SDK drive 해석/PD포화·구동법칙의 유일원인·변형 입력의 native 정착은 미확정이다. 외부문서를 추가로 쓰면 primary source만 인용하고 추론을 구별한다.

분석 후 후속116 설계는 정확한 입력변경 한 가지만 택한다. 후보의실제소비경로(생성/producer/독립consumer/workspace/숫자역할IR)와 gate 불변을 명시하고 종전class/sourceEXH를 복사로 초기화하지 않는다. 후속 native가필요하면 **새첫원격부터2700초 단일시도·import1→정지1→motion1·retry0**, 기존20/cleanup2/native600/motion900/headroom을 유지하는 구체 제안으로 남긴다. 다음 실행의관측성·기각조건을 함께 명시한다. 이115는 그 새운영소스/활성화/원격시계를 만들지 않는다.

## 8 이진 수용 기준

- AC1 권한/보호: offline0remote/SDK/실물false·원문/해시/foreign WIP보존.
- AC2 입력: 정확 report/저널·5041연속투영·현재 pin 대조·변조거절.
- AC3 참조: 실제 source 함수+독립수식·9축 전시점/경계·유한성·binary32/한계 검산.
- AC4 원판정: 실제checkpoint6개·34초 원실패/42초통과·전체false 유지·9축 연속범위 분리.
- AC5 원인한계: 실제관측/설정/경험fit/추론 분리·PD sensor/물리수용 오표시0.
- AC6 후보: 비활성·동일8초/endpoints/deadline·속도·가속도tradeoff·native예측0·consumer 미지원명시.
- AC7 재현: 소유스크립트·의미양음성/회귀·source핀/독립검산·판정수치의문서동기.
- AC8 종결: 비작성자L2/L4·유한원장/기존소진/공통편향·인계·선별localcommit/push0·구체다음범위.

115의 PASS는 위 오프라인 분석/후보의 재현성이다. 원114 native settling실패나116 미실행을 PASS로 바꾸지 않는다.
