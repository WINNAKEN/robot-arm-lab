> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 087 — 모듈 없는 CAN 읽기 진단 실행부 준비

2026-10-30 · 사용자 구현 지시: 읽기 전용 진단 실행부를 준비하고 모듈 없이 검증한다. 보정·모터 운전·플래시는 제외한다. 첫 시계13:38:28UTC, M단위45분 상한14:23:28UTC, L2/L4 각최대2회. 기존085/086 예산·실행 원장은 재사용하지 않는다. 외부 검토 bridge의 이전 자동심사 거절은 우회하지 않고 동일계열 비작성자 폴백 편향을 기록한다.

## 입력과 범위

사용자 주문 화면은 Waveshare ESP32-S3-RS485-CAN-U다. 모터/드라이브는 도착 보고이며 사진의 모터 라벨에는 SERVO42D_485가 보인다. 모터 몸체 라벨만으로 부착 드라이브의 CAN/RS485 옵션을 확정하지 않는다. 드라이브 PCB 단자 표기/HW/FW/실물 CAN 리비전은 미확인으로 유지한다. 해당 사진을 원문·해시와 함께 intake에 보존한다. CAN으로 추측해 급전/연결하지 않는다.

한 기능 M단위의 소유: 새 `src/firmware/components/robot_diagnostic/`(header/cpp/CMake), `src/firmware/tests/diagnostic/`(C++시험/run.ps1), 새 독립 `src/firmware/diagnostic/`(rootCMake/mainCMake/main.cpp), 본 계획/진단사용문서와 `.dev/can-readonly-evidence/`·최소인계. 기존app·core·CanPort·TWAI·Boot/Run·웹·CAD·URDF·BOM·기존체크리스트/엑셀은 읽기만 한다. 설치·SDK실기동·Isaac접속·플래시·CAN장치·모터급전·재부팅·구매 없음. 독립 타깃은 기존ESP-IDF5.5.6/S3 전제의 준비 코드이며 실제SDK빌드는 이번 단위 완료조건에 넣지 않는다. SDK호환은 stub compile과 기존포트사용형식까지, 실제target빌드는 NOT_RUN으로 구분한다.

## 읽기 전용 계약

진단 객체는 CanPort 단일 소유 수명으로 구성한다. 생성/기본프로필은 I/O 없음. 실제protocol/단자/bitrate/전원시무운전조건·selectedaxis1/2·하드웨어검토가 명시적으로 확인되지 않으면 시작 전에 거절한다. HOST의true프로필은 합성시험fixture이며 실물승인값이 아니다. 독립S3 app의 실제승인은 컴파일상false와static_assert로 고정하고 외부설정으로 바꾸지 않는다. 기본main/CMake는 변경하지 않는다. 앱에는 네트워크/웹/사용자raw송신API/승인메뉴를 만들지 않는다.

한 세션은 한 ID에 한 번만 3A→F1→31→32를 요청한다. TX직전 실제WireFrame의ID/표준DATA/RTR/EXT/DLC2/opcode허용4종/checksum/미사용바이트를 다시 검증한다. enum선택만 믿지 않는다. 공개raw송신·설정쓰기·F3/F7·이동·보정·홈·heartbeat·ID/bitrate쓰기는 없고 자동재시도·busoff복구·세션재시작도 없다. F1 F3의두번째바이트처럼checksum이F3인정상읽기는허용한다.

새포트수명/빈TX/RX·오류counter0·정상bus·알림0 확인 뒤 단일inflight로 시작한다. 접수와TX_SUCCESS를 구분한다. poll은단조ms로10ms미만, 격리/시작100ms미만·한submit10ms미만을소프트웨어검사한다. 요청TX완료250ms/응답500ms/조회사이150ms/전체4000ms는 이새진단의 보수적HOST시험후보이며 실물지연/정지성능 승인이나 기존정지기준변경이 아니다. 경계는>=만료, 성공보다만료우선이다. submit직전/직후시각, dequeue시각·실제RX·파싱값·오류를 고정용량저널에 남기며 용량초과는fault(조용한덮어쓰기없음)다. I/O시간/시계역행/누락timestamp/드라이버오류/unknownalert/fatalalert/counter변화/중복·추가RX/잘못된ID·flags·DLC·checksum이면fault/close한다. 단일선로모든사건의하드웨어시각을관측했다고주장하지않는다.

읽기전TX완료전RX는수용하지않는다. TX250ms와응답500ms는둘다submit직전단조시각기준이고조회사이150ms는유효응답처리후부터다. 수신dequeue시각은0을미확인예약값으로거절하고submit이후·현재이하인지확인한다. 포트에하드웨어timestamp/validityflag가없어이제약을명시하며선로도착시각으로대체하지않는다. 매읽기에서원프레임과건강/시각을대조하고마지막값을받아도batch잔여/health를확인한다. enable1/F1조회실패0·운전/홈/보정2~6이면운전조건불일치로중단하고쓰기명령으로수리하지않는다. 위치는signed48원시값·속도는signed16rpm으로만기록한다. 영점/각도변환없음. healthy+quiesced close와최종시간검사까지통과해야READS_COMPLETE이며 물리정지/무토크/실물통신수용판정이아니다.

## 검증 순서

L2→새컴포넌트/독립비활성entry→strictC++17 HOST/FakeCanPort·SDKentry stub compile→source동결→비작성자L4. 프로필거절무I/O/생성무I/O/ID1·2각4회/전프레임허용목록/모든opcode대조/실제TX완료대기/정상값부호/enable1/F1각실패값/timeout경계/시계역행/submit지연/RX시각·flags·DLC·checksum/중복RX/버스·counter·alert·close실패/close중시간위반/저널가득/terminal후무I/O를시험한다. 순서·허용opcode·기한변형은별도임시소스로검출하고원소스는변경하지않는다. 기록·가짜포트·비활성app결과와실물NOT_RUN을구분한다.

완료물은사용법·원로그필드·도착후확인할미정값·HOST결과/원출력/동결해시다. 전체기존FW시험을중복재실행하지않고변경없음해시로기존core/TWAI를대조한다. 기준을임의완화하지않고검토차수/시간을넘겨반복하지않는다.
