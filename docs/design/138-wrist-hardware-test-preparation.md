> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 138 — 조립된 그리퍼·J5·J6 결선 및 제어 시험 준비

2026-11-11 KST. 사용자: 「그립퍼와 j5,j6를 조립완료…제어 관련 테스트를 진행할 준비…결선도…소프트웨어적으로 테스트를 준비」. 사진은 조립 보고의 근거이며 단자/모터 정격/드라이버 통신형/감속비/출력 버전 결속의 확인 근거는 아니다. 기존 RS485 임시 시험→CAN 최종 통합 방향을 유지하되 현품 변경 여부를 질문했다. 미응답이면 미확인으로 남긴다.

## 범위와 소유

새 준비물만 만든다. 실제 포트 열기/열거·UART/CAN 송수신·플래시·급전·움직임·SDK/SSH·네트워크 변경·설치·구매·Drive 업로드·Git 변경은0. 원 CAD/URDF/STL·원장·펌웨어·시뮬137 및 이전 기록/게인/cap/판정 기준은 불변이다. hardware_approved=false, physical_tests=NOT_RUN. 과거 승인·소진/라운드/실행권한 재활성화0.

작성자 소유(기존 파일 변경 금지):

1. `src/bench/wrist138/protocol.py`
2. `src/bench/wrist138/bench.py`
3. `src/bench/wrist138/profile.template.json`
4. `src/bench/wrist138/test_bench.py`
5. `src/bench/wrist138/firmware/CMakeLists.txt`
6. `src/bench/wrist138/firmware/main/CMakeLists.txt`
7. `src/bench/wrist138/firmware/main/main.c`
8. `src/bench/wrist138/firmware/sdkconfig.defaults`
9. `docs/specs/wrist-bench138.html` (인쇄 가능한 한국어 가이드+inline SVG 결선도; 별도 SVG/README 생성 안 함)

계획 포함10파일/M, 그룹2(현품/결선/프로필, 오프라인 소프트웨어·읽기 전용 중계). 증거·build 산출은 `outputs/wrist-bench-prep-138/` 아래 전용 author/review/Root 영역. 추가 제품 파일이 필요하면 Root에 사전 보고한다. Root만 HANDOFF를 이전 바이트 보존 prefix, SESSION_HANDOFF를 append한다.

L1 Root→비작성자 L2→별도 작성자 L3/HOST→비작성자 L4→Root 최종 오프라인 실행. 각 role 내부2700초/main L2+L4 공유2700초, 준비/실행/수리/출판 누적, 명시 frozen 대기만 제외, closing300초. L2/L4 각각 최대2/총4/no5. 기존 동일계열 비작성자 폴백 승인은 유지하되 편향을 잔여로 기록한다. 새 사용자45분 승인이나 원격 실행 승인이 아니다. 작성자 code0 before FINAL L2 PASS. 새 실제 결함 계보·EXH는 비작성자 판정, 원137/136/135/134는 무수정이다.

## 자료와 결선

1. 로컬 Makerbase 공식 RS485 V1.0.9 PDF SHA `11ed701c9fdc8c450c62d8a25649ea94033c93e993192bcd81c236caa00bf9f0`를 읽는다. p9 12–24V 제품 범위(현품 승인 전 설정값 아님), p10 단자, p19 짧은 단독 RS485 무종단 및 다중 버스, p23 설정, p26 FA/FB·big-endian·sum8, p28 31 signed48/32 signed16, p30 3A enable, p74 F1 state, p75 F3/F7, p81–82 FD pulse move/stop. 문서 p28 CW/CCW 서술과 예시가 반대인 점은 sign 추측 없이 실측 방향 대조 대상으로 둔다.
2. Waveshare 공식 https://docs.waveshare.com/ESP32-S3-RS485-CAN 및 /FAQ, 기존 공식 회로 `.dev/can-evidence/wiring/waveshare-schematic.pdf`와 GPIO table 그림: RS485 TX17/RX18/RTS21, CAN TX15/RX16. GPIO21은 고정 HIGH enable가 아니라 UART half-duplex 방향제어다. USB와 DC 단자 동시급전 금지. 외부 A+/B−, H/L만 보이므로 절연 SGND를 논리 SH1.0 GND에 임의 연결하지 않는다.
3. 결선도는 현품 위치가 아닌 **단자 이름**으로 연결한다. 기본은 Waveshare USB만 급전, 모터는 별도 검증된 DC(모델 공통범위가 아니라 현품/모터로 결정), DC 정격 차단·분기 퓨즈→각 V+, PSU−→각 전원GND. 구체 퓨즈/전선 굵기/전류 설정은 미확인으로 남긴다. MKS EVCC 5V/20mA는 모터/ESP32 전원으로 쓰지 않는다. 모터 코일 A±/B±와 통신 A/B를 명확히 구분한다.
4. 처음은 한 축만 전원/통신 연결하고 다른 두 축은 전원 OFF 및 물리 분리한다. 모든 공장주소1인 세 드라이버를 함께 연결하지 않는다. 축별 ID1/2/3은 제안일 뿐 실제 주소 확인·한 대씩 설정 후 다중 버스로 확장한다. 자동 주소변경/스캔/동기실행은 없다.
5. 짧은 RS485 단독 구성은 MKS p19 무종단·Waveshare NC 준비안과 현품 확인을 적는다. 다중 RS485와 CAN은 별도 선형버스 그림/양끝 종단·중간OFF 계약으로 구분하며, 현재 단독 RS485에 CAN 60Ω 합격표를 적용하지 않는다. CAN형 드라이버 교체가 필요하고 RS485형을 선만 바꿔 CAN으로 만들 수 없다. 기존 CAN actor가2축 준비물임을 명시하고 3축 물리 수용으로 확대하지 않는다.

## 소프트웨어

Python은 stdlib만, 저장소 입력/출력만 사용하며 serial/socket/subprocess transport·COM 옵션이 없다. CLI는 `status`, `demo`, `read-plan --axis ... --address ...`, `decode --address ... --code ... --hex ...`, `jog-plan ...` 등 의미가 명확한 오프라인 기능을 제공한다. 실제 통신이 없음을 JSON에 명시하고, 예시 응답은 항상 synthetic이다. 출력은 stdout 기본, 파일은 선택된 새 전용 leaf/xb로 보존한다. 임의 root 경로/기존 파일 덮어쓰기 기능은 없다.

프로토콜은 MKS 직렬 FA/FB sum8과 CAN 프레임을 혼용하지 않는다. read whitelist31/32/F1/3A, 주소1..255/bool거부/방송0금지, 정확 헤더·주소·opcode·길이·checksum·상태값·signed big-endian. 한 응답만 소비하고 trailing bytes/부분응답을 성공 처리하지 않는다. F1 0은 query failure이며 stop1과 구분한다. checksum 통과만으로 FW/기구/정지 성공을 선언하지 않는다.

`jog-plan`은 모터 회전량/출력축 회전량/그리퍼 랙 이동량을 분리한 **예정 프레임**만 계산한다. motor step angle·microsteps·gear ratio·기계 중립/방향·이동 여유·모터 전류/전원/고정/차단/모드/FW/교정/자동복귀 등의 실제 확인이 빠지면 BLOCKED 사유를 전부 내며 FD/enable payload를 내지 않는다. 시뮬 게인/토크cap이나 CAD 가정27:1을 실제 승인값으로 쓰지 않는다. 실제 확인 프로필을 복사해 순수 합성 HOST fixture에서만 양성 통과를 검증한다.

이동 계획의 첫 보수 소프트웨어 상한은 모터축1회5deg 이내·5rpm 이하·양의 가속 설정·양의 pulse·단일 축/단일 유한 이동이다. 이는 안전 인증/실물 사용 승인값이 아니며 실제 기계 허용범위가 더 좁으면 그 값을 쓴다. 출력각을 크게 요청해 모터 상한을 우회할 수 없고 반올림된 pulse의 실제 모터/출력 이동량을 재검산한다. 그리퍼는 r13.5mm/gear ratio를 현품 확인하기 전 mm 제어를 열지 않는다. 상대 이동 재전송/연속속도/홈/교정/파라미터쓰기/자동 enable/동기그룹 명령은 없다. 이동 시작·완료·새엔코더/속도·실제 관찰·정지 검증을 이후 시험 기록 양식에 분리한다.

ESP-IDF 별도 standalone target은 **읽기 전용 USB→RS485 중계**다. 원 app_main/robot_* 무변경. sdkconfig 기본 hardware permit false, 이 기본값은 UART/USB 장치 초기화·TX0으로 종료한다. 준비 펌웨어를 실제 사용하려면 현품/모드/baud/프로토콜/버전을 확인하고 별도 사용자 실행 승인이 필요하다. 선택적으로 permit true로 빌드한 준비 artifact도 이번에는 flash/실행하지 않는다.

허가된 코드 경로에서도 고정 bounded ASCII `READ addr code`만 수용하고 네 read opcode에 한해 **한 요청4바이트를 한 UART write**로 보낸다. UART1/TX17/RX18/RTS21, HALF_DUPLEX driver 사용(정적 GPIO21 HIGH 금지). baud38400/8N1은 V1.0.9 대비 준비 후보이며 실제 현품 설정 확인 전 적용 승인 아님. 입력 길이/범위/큐 적체·이상문자/timeout/짧은·잘못된 응답을 실패 처리한다. 한 번에 요청 하나, 자동 retry/주소스캔/기동TX/enable/F3/FD/F7/설정변경이 없다. USB request parser와 실제 UART write seam을 HOST stub으로 직접 실행해 금지 입력 TX0과 정확 full4byte TX를 확인한다. EOF/timeout/오류가 다음 명령의 유효 조각이 되지 않게 폐기/동기회복 규칙을 테스트한다.

기존 설치 IDF/컴파일러만 사용하고 다운로드는 없다. 기본 비활성 target build를 시도해 build/환경실패를 raw 보존한다. prepare/허가된 분기의 HOST가 실제 main.c를 소비했는지 기록한다. IDF 빌드가 환경 때문에 미도달이면 미빌드라고 표시하며 stub 통과를 target build로 바꾸지 않는다.

## 시험·보고·수용

수용 AC8: 1 사용자 범위·원본 보존/미확인 사실 2 제조사/현품 구분된 결선·절연·전원/종단/코일 구분 3 strict frame+signed/status parsing 4 전체 unknown일 때 이동BLOCKED/비유한bool범위·rounding/기어·단위 오류 차단 5 실제 CLI synthetic 구분+read/jog양음성 6 실제 main.c HOST seam의 요청parser/단일UARTwrite/기동TX0·금지opcode·timeout/부분프레임 7 로컬 target build 결과 정확 기록/문서 이미지 실제 시각검사 8 sourceF·원시결과·nonauthor/clock/라운드/class/publication 일치.

실물 시험 순서는 전원OFF 결선/극성/단락 검사→기구 고정·중력축 J5 받침과 무급전 처짐 대책→한 축만 현품 설정/자동재개OFF 확인→읽기만→정지/차단/재시작 확인→별도 승인된 극소 유한 이동→축별 방향/감속비/유격 측정→다른 축→향후 CAN 재검증이다. 조립된 기어/하중을 연결한 채 자동 교정을 시작하지 않는다. 미확인 교정 이력은 자동교정 명령 대신 BLOCKED 조건이다. 정지ACK는 실물 정지 보증이 아니며 단절 시 소프트웨어 정지전달 불능과 J5 중력 처짐을 문서에 반영한다.

최종 결과는 사용자가 바로 읽을 수 있는 한국어 결선 HTML, 오프라인 명령 예시/설정 템플릿, 검증된 read-only 준비 코드와 HOST/target-build 상태, 미확인 표다. 장치 시험은 NOT_RUN, 실제 RS485/모터 이동 준비의 남은 확인 항목을 숨기지 않는다.
