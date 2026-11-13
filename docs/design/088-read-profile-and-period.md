> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 088 — 읽기 프로필 준비와 ESP32 주기 검증

2026-10-30 · 사용자 구현 지시. 실물 보정·모터 운전·플래시·급전·CAN장치·Isaac접속은 제외한다. 첫 시계14:33:36UTC, M단위45분 상한15:18:36UTC. L2/L4 각각최대2회, 실제ESP-IDF타깃빌드1회(기존설치만,최대360초/전체종료120초앞까지), 자동SDK재빌드없음. 기존087 원자료·동결·빌드는 보존한다.

## 소유와 범위

한 읽기 실행기능의 코드변경은10파일이내다: robot_diagnostic/execution.hpp 신규, 기존diagnostic.hpp/.cpp의schedule-only abort, 독립diagnostic main.cpp·CMakeLists·sdkconfig.defaults, 기존HOSTtest_diagnostic.cpp/run.ps1, 새evidence/entry시험helper·target빌드wrapper. 계획/프로필기록template/사용문서/검토·원자료는부속산출물이다. 기존운전main/Boot/Run/core/CanPort/TWAI/웹/CAD/URDF/BOM·086엑셀은변경하지않는다. source087 freeze는수정하지않고새088 freeze로version을구분한다. 소유evidence `.dev/can-read-profile-evidence/`, docs/design/088*, docs/specs/read-diagnostic-profile.template.json와읽기프로필/주기사용문서,최소인계다.

## 프로필

예상보드CAN-U·CAN-protocol·TX15/RX16·500k·선택ID1/2와실제관측값을분리한다. 실제보드/드라이브프로토콜/핀/bitrate/ID/HW/FW·배선/종단·전원시자동동작배제는기본미확인이다. 사진모터몸체_485라벨은드라이브프로토콜확정값이아니다. 기록용JSON은expected/observed/미확인필드를분리하고실행시로드하지않는다. 문자열은고정길이이내·비공백·제어문자없는기록인지검사하되내용만으로측정사실이나CAN을인증하지않는다.

순수평가함수는Pending/Mismatch/ReadyForReview와구체적issue bit를돌려준다. 모든관측이맞아도생성Profile.hardware_approved는항상false이며ReadyForReview는실물허가가아니다. 문자열borrow를반환상태에보관하지않고검사결과/숫자만보존한다. 기존native immutablefalse/static_assert와기본Profile거절을유지하며메뉴/JSON/웹/시리얼에서활성화할경로를추가하지않는다. HOST에서Runner에true를주는것은Fakefixture뿐이다.

## 주기

독립진단타깃의sdkconfig.defaults에FREERTOS_HZ1000을선언하고CMake에서그기본값경로를고정한다. 실제CONFIG_FREERTOS_HZ1000·pdMS_TO_TICKS(1)>0를compile-time확인한다. 외부기존sdkconfig가100Hz라면조용히통과시키지않고실패한다. 기존일반운전타깃설정은그대로다.

단조ms기반순수Cadence는1ms후보주기에한번만Runner를poll한다. 같은시각/이른호출은무송신,시계역행·직전서비스부터10ms이상은schedule fault로Runner를닫는다. 늦게깨어나도밀린횟수만큼연속poll하지않고관측시각당최대1회로제한한다. 종료뒤추가I/O없음. Runner의기존10ms/250/500/150/4000 조건은그대로다.

실제main은xTaskDelayUntil로1tick절대주기를기다린다. 대기함수가이미늦어pdFALSE를반환하면catch-up반복대신schedule abort로종료한다. 이abort는새Error::Schedule을끝에추가하고CanPort.close만호출하며F7/토크명령을보내지않는다. 공유service helper를HOST의실제Runner+FakeCanPort에도연결해early/due/9ms/10ms/역행/대기실패/끝난뒤무I/O를대조한다. 물리RTOS/ISR실행은NOT_RUN이며1000Hz컴파일설정만으로1ms실물서비스보장이라주장하지않는다.

## 검증

L2→구현→strictC++17 HOST/프로필필수필드누락·불일치·모든필드일치해도하드웨어false/합성valid profile·Cadence와Runner통합·087읽기회귀·3기존변형+프로필승인오염/주기10ms완화변형→source동결→L4. 실제mainSDK선언stub에서1000Hz비활성·구성승인무시/CAN·스케줄러호출0,100Hz/0tick은compile拒否한다. 기존SDKv5.5.6으로새evidence안의비활성project1build,실제config1000Hz·새main/진단/codec/TWAI compile경로·기존운전main미포함·ELF/BIN/hash·source전후동일을확인한다. source/HOST 검토뒤타깃확인과최종검토를같은L4R1의연속관측으로묶거나필요시R2를사용한다. 최종문서에서087의100Hz기록을덮어쓰지않고088추가검증을구분한다.

SDK빌드의일회/timeout/자기PIDtree종료·숨김실행·실패nonzero/원로그보존을유지한다. 설치/setup/flash/port명령은없다. 기존외부bridge자동심사거절을우회하지않고같은계열비작성자폴백의공통편향을기록한다. 완료는프로필/주기HOST+비활성타깃컴파일범위이며실물통신·정지·토크수용/최종6축지원이아니다.
