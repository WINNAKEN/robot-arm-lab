> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 144 — 조립 유지·모터 OFF ESP 조회 전용 펌웨어 업로드

사용자가 모터 전원 OFF·조립 유지 상태의 ESP 조회 전용 펌웨어 준비/업로드를 명시 승인했다. 모터 급전·Ma 변경·enable·회전·CAL·원점복귀는 제외한다. 기존143의 비활성 준비/예산은 동결한다. 새 M 단일그룹(제품 최대10파일), Root/비작성자 각2700초·마감300초. reviewer L2<=2/L4<=2/총4. 기존 동일계열 비작성자 폴백 승인 유지, 표준 agent-bridge.py는 이번에도 기존 hard-coded Windows path lint로 실행 차단됨. 외부 계열/같은 컴파일러 편향은 결과에 남긴다.

## 구현과 소유

새 src/firmware/can_reader144/ 안 CMakeLists.txt·sdkconfig.defaults·partitions.csv·main/CMakeLists.txt·main/main.cpp·main/protocol.hpp·main/flow.hpp, src/bench/test_can_reader144.cpp, docs/specs/can-reader144.md, 본계획 및 outputs/esp-readonly-flash-144/ 증거/한정 실행 스크립트만 소유한다. 제품10파일/M단일그룹이다. 구 diagnostic entry·prepare_profile·CAN 제어 모듈·143 freeze는 수정하지 않는다. HANDOFF 두 파일은 덧붙이기만 한다. 새 펌웨어는 일반 제어 app이 아닌 별도의 USB 요청형 조회 브리지다.

ESP-IDF5.5.6 현존 도구만 사용, 설치/다운로드 없음. USB Serial/JTAG console/driver로 INFO 및 정확한 READ <decimal ID1..16> <bitrate125000|250000|500000|1000000> <31|32|F1|3A> 한 줄만 처리한다. 부팅·INFO·잘못된 입력에서는 CAN 미설치/송신0. Generic RAW·scan·설정·F3·F6·FD·FE·FF·CAL·홈·enable은 제공하지 않는다. 제한길이 ASCII parser, overflow는 newline까지 전부 버린다. GPIO15TX/16RX는 사용자 non-U의 제조사 기대값으로 명시하고 현품 관측으로 가장하지 않는다. READ는 미래 사용자가 실제 CanID/rate를 확인해 지정할 때만 보낸다. 현 단위는 업로드후 INFO만 호출하며 READ는0이다.

1요청은 표준 DATA/DLC2 {opcode,(id+opcode)&255} 1회 single-shot(TWAI_MSG_FLAG_SS), 재전송/자동scan/주기poll 없음. normal TWAI 세션의수신은 최대250ms, 설치/송신/정리 제한시간을 별도로 명시해 전체가 유한하도록 한다. 응답 ID/opcode/DLC/CRC를 검증해 raw data JSON으로 반환한다. RX flood도 절대 deadline/frame수로 제한, 매번 stop/uninstall. 정리 실패는 latch로 이후READ 금지. no driver installed on idle; controller ACK는 미래 READ 세션에만 생길 수 있음을 명시한다. 실제 main이 사용하는 shared flow.hpp transport 흐름을 fake backend로 HOST 검증한다: install/start/transmit/receive 실패, timeout, 잘못된 응답/CRC, RX flood, stop/uninstall 실패, latch 후 재요청 무송신·무재설치, single-shot/DLC2/1요청1전송을 포함한다. USB parser 정상/잘못된 ID·bitrate·금지op·overflow·binary와 소스/바이너리 출력 경로도 검토한다.

## 읽기·복구와 배포

실물은 COM7 VID303A/PID1001 단일 ESP32-S3인지 OS열거 재확인한다. 모터 OFF는 사용자 지시/보고이며 원격 계측 아님. ESP ROM flash_id/get_security_info만 먼저 조회. Secure boot/encryption/secure download이면 force하지 않고 중단. actual flash16MiB가 확인될 때만16MiB config를 사용하며 다른 크기는 먼저 계획/설정을 수정·검토한다. 기존 app0/app1/partition 헤더는 실제 full backup과 비교한다.

쓰기 전에 공식 esptool로 전체 flash를 파일로 read_flash하고 verify_flash로 읽기 백업을 재검증(또는 독립 두번째 read와 전바이트 비교)한다. backup은 해당 보드의 개인정보 포함 가능성이 있어 local-only/Git/Drive 업로드 없음. 크기·SHA256·geometry·보호상태·장치식별 로컬 manifest와 기존 partition/otadata/app0 범위의 복구 이미지를 남긴다. ROM/reset/RAM stub 사용은 기록하고 flash쓰기와 구분한다. 모든 호출 외부 timeout/returncode/log을 남긴다.

원칙은 기존 bootloader/partition table/NVS를 보존하는 app0-only 배포다. actual partition table에서 OTA app0 offset0x10000/size가 새 앱을 수용하고, otadata0xe000/size0x2000을 확인해야 한다. IDF app의 기존 bootloader 호환 설정/공식 근거를 검토한 뒤 app0와 초기 otadata만 write_flash한다(전체 erase/force/eFuse 변경 금지). bootloader 호환이 확보되지 않으면 쓰기 전에 중단/계획수리한다. 단 한번의 배포와 readback 검증 후 USB INFO의 project/version/boot-id·CAN_idle/TX0/허용목록을 확인한다. 부팅 실패면 검증한 기존 app0/otadata 바이트를 복구해 되돌리고 실패 보고한다. 새로운 bootloader/table로 무검토 확대하지 않는다.

복구 트리거는 첫 write 시도 이후의 모든 쓰기 timeout/nonzero·readback 불일치·INFO 미응답/잘못된 앱/반복 reset에 적용한다. 같은 보드인지 고유식별을 재대조한 뒤 검증한 original app0 전체범위와 otadata를 1회만 복원하고 readback 전바이트를 대조한다. 복원 성공/실패/장치접근불가를 구분하며 복원 실패를 완료로 처리하지 않는다. 첫 write 전 실패는 flash 변경0으로 중단한다. backup/후보/복구 파일 SHA와 정확쓰기범위를 pinned manifest에 고정한다. 전체 백업을 임의 다른 보드에 복구하지 않는다.

L2 PASS → 구현/HOST/빌드 → L4 PASS(실물쓰기전, exact frozen source/build/deployment) → backup/flash/readback/USB INFO. 전쓰기까지 백업 등 읽기 진단은 허용하되 쓰기 전 검토 통과가 필수다. 실물 결과는 Root가 검토된 실행계약과 대조한다. 기존143 결과/핀이 새 단위 파일로 오염되지 않게 새 build dir 사용. 실제 CAN응답/배선/모터정지 검증이 완료됐다고 말하지 않는다.

AC1 boot/invalid/INFO CAN TX0. AC2 유효조회4종만, single-shot/bounded/cleanupfail latch. AC3 compiler USB build와 meaningful HOST/부정대조. AC4 exact backup/identity/geometry/security/target 범위와 restore 확보. AC5 reviewed binary flash readback+real USB INFO 확인. AC6 모터OFF/조립유지·CAN READ0·부족한 현품 관측·동일계열 검토 한계를 정확 인계.

