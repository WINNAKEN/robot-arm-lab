> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 143 — 사용자 non-U 보드의 J5 조회 준비 지원

2026-11-12 KST. 사용자의 현재 요청은 모터 무급전 ESP 펌웨어 확인과 J5 CAN 시험 준비다. 141/142에서 COM7·ESP32-S3rev0.2·app0 저장헤더 arduino-lib-builder/IDF5.1.4계열·app1앞4KiB FF를 확인했다. 실행 앱/기능은 미확인이고 쓰기/호스트CAN요청/모터급전은0이었다. 사용자 보드는 ESP32-S3-RS485-CAN(U 없음)이다. 준비 과정에서 기존 native 진단이 CAN-U enum만 허용하는 소프트웨어 불일치를 확인했다. 이 알려진 준비 결함을 오프라인에서 해결한다. 추가 실물 접근은 하지 않는다.

## 범위와 선택

- Board enum에 WaveshareCan(non-U)을 추가하되 기존 Unknown=0/CanU=1/Other=2 값을 보존한다. prepare_profile의 보드 모델 허용집합만 두 공식 변형으로 확장한다. 두 모델의 실제 리비전/핀/펌웨어/ID/bitrate/배선/전원투입동작 관측 요구는 유지한다. ReadyForReview는 hardware_approved=false를 계속 반환한다. native app의 kPhysicalReadApproved=false/static_assert를 변경하지 않는다. 실제값 누락 시 Pending, 잘못된 모델/설정은 Mismatch이며 활성 CAN이 열리지 않는다.
- 로컬 준비 Python의 'CAN-U만지원' 상태 문구를 현재 native 지원과 일치하도록 BLOCKED_UNCONFIRMED_PROFILE로 바꾼다. 실제ID/bitrate/GPIO=null, hardware_approved=false, default frames=[]와후보1/2 오프라인프레임·수신/ROM파서 기능은 그대로다. 기존141 안내는 역사적 상태이며 최신143 안내가 이를 대체한다고 명시한다. 과거141/142 증거·판정·clock은 수정하지 않는다.
- 기존 공개 Waveshare 제품군은 non-U/U를 안테나 변형으로 설명하며 로컬 공식GPIO표에서CAN TX15/RX16을 제시한다. 이를 보드별 기대값의 근거로만 사용하고 실제 배선/리비전 관측으로 승격하지 않는다. CAN-U로 가장시키거나 체크를 우회하지 않는다.
- HOST C++에서 실제 prepare_profile의 non-U/U/Unknown/Other·누락/불일치·기존 enum 값·ReadyForReview에도 물리승인false를 검증한다. Python HOST와 실제CLI로 변경된 문구/실제null/송신없는후보프레임 보존을 확인한다. 가능하면 기존SDK5.5.6으로 diagnostic 기본 비활성 이미지를 새 출력경로에 빌드한다. build만하며 flash/monitor/포트접근은0이다. 자동설치/의존성다운로드/네트워크가 필요하면 빌드를 중단하고 미완료로 기록한다.

## 소유·검토

M/단일그룹/제품6파일: 이 계획, execution.hpp, src/bench/j5_can141.py, src/bench/test_j5_can141.py, 신규src/bench/test_j5_nonu143.cpp, 신규docs/specs/j5-can143.md. 증거는outputs/j5-nonu-profile-prep-143/. Root 작성/구현·비작성자 L2→HOST→L4. 각role 새2700초/closing300, reviewer L2/L4 공유, 각max2/총4/no5. 기존 동일계열 비작성자 폴백 승인·공통편향 잔여 유지. 다른 작성자 파일/원CAD/원장/그리퍼/게인cap/성능판정/기존종결자료는 바꾸지 않는다. 변경 전 기존3수정파일 및141/142 관련정본을 새evidence에 바이트 보존하고 intentional hash delta를 기록한다.

141의Root1515.9827566/1500초 초과·closing미달과reviewer910.0059496/4of4,142reviewer377.7487522/2of2는 그대로 동결한다. 이번은 그 시간 초과 수리나 검토기회 재개가 아니라 사용자 실모델 지원이라는 새 준비 범위이며 과거 전체절차PASS를 만들지 않는다. 모터전원·UART/CAN/USB 실물 접근·업로드/삭제/교정/이동·설치·네트워크·원격·Git·Drive0이다. 현재 미확인J5 HW/FW/주소·속도·전원·상전류·고정/차단·종단은 null/대기로 유지한다.

AC1 기존enum값/호출부보존과non-U 명시지원. AC2 실제관측 요구/잘못된값거절/ReadyForReview물리승인false·entry불변. AC3 Python상태정합·실제null/오프라인프레임/수신/헤더기능보존. AC4 실제native/Python HOST·필요한기계검증 및실제빌드결과/미완료구분. AC5 원본·141/142역사/clock/의도된차이증거 보존. AC6 최종문서에서기본비활성후보와실제CAN운전허가·저장헤더식별·미확인하드웨어를구분하고정확인계/공통편향을기록.
