> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 142 — 두 OTA 저장칸의 메타데이터 확인

2026-11-12 KST. 사용자의 현재 지시(모터 전원 OFF 상태에서 ESP 펌웨어 확인·J5 CAN 시험 준비)를 계속한다. 141의 첫 실제 파티션 read는 성공했지만, app0/ota_0=0x10000·3MiB와 app1/ota_1=0x310000·3MiB를 관측했다. 141의 단일 앱 조건은 실제로 거절되어 앱 read0회로 종료했다. 이는 기존 앱 식별을 완료했다는 뜻이 아니다.

새 문서 전용 S 2파일은 이 계획과 docs/specs/esp-slots142.md이며, 기존 코드 변경/새 코드/flash 재시도는0이다. 증거 위치 outputs/esp-stored-slot-142/. 기존141 source-freeze-F2와 reviewer L4-R2/clock은 불변이다. 141 Root author clock은1515.9827566/1500초(15.9827566초 초과)·closing reserve 미충족으로 기록된 채 보존하며 이를 PASS나0초/새carry로 고치지 않는다. 기존 reviewer는910.0059496/1500초로 종료했다. 이번은 그 검토/수리 기회의 재개가 아니라 새로 관측한 다중 저장칸을 활성 앱으로 추측하지 않고 조회하는 제한된 후속 조작이다. 구현 수리는 하지 않는다.

기존 SDK gen_esp32part.py가 실제 partition.bin의 MD5/엔트리/배치를 검증하고 CSV를 생성했다. 141의 엄격한 parser도 'Exactly one stored app required'까지 도달했다. 후속 조작 전에 partition.bin SHA와 파티션 엔트리 두 개의 실제 주소/크기/flags=0을 다시 대조한다. NVS/otadata/FFAT/coredump는 읽지 않는다.

허용: COM7 VID303A PID1001, 사용자 실제제품 ESP32-S3-RS485-CAN(non-U), 모터 OFF 사용자 보고/미계측. 기존 esptool4.12.0 read_flash만 사용하여 두 저장칸 각각 첫4KiB를 고정 주소0x10000·0x310000에서 한 번씩 읽는다. flags는 --chip esp32s3 --baud115200 --before usb_reset --after hard_reset --no-stub --connect-attempts1. 각 새 프로세스45초/총2회/재시도0이다. 기존141의 남은 세션을 재사용하지 않고 이 후속 범위의 두 읽기를 별도 기록한다. firmware/flash write·erase·RAM stub·eFuse·설정·앱명령·CAN요청·모터급전·구동·설치·원격·Git·Drive0이다. 첫 읽기 실패/timeout/보호이면 다음도 수행하지 않는다. 정상 read한 slot이 전부0xFF 또는 구조 불일치면 빈/미검증 칸으로 기록하고 재읽지 않는다.

기존 검토된 j5_can141.py app parser로 슬롯별 저장 메타데이터만 판독한다. 결과는 '저장 슬롯의 project/version/IDF/build/ELF 기록값'이며 현재 실행 슬롯·전체 이미지 무결성·서명·원본 소스·CAN 안전성을 확인한 것으로 쓰지 않는다. 두 앱칸이 있어도 실제 두 유효 앱이라는 뜻이 아니고, 한쪽 prefix가FF여도 현재 실행 중인 앱이나 안전한 부팅을 단정하지 않는다. USB ROM 요청/리셋은 발생하며 앱 복귀 후 ESP 자체CAN활동과NVS변경은 NOT_MONITORED다. 호스트 CAN요청0/모터시험NOT_RUN과 구분한다.

Root 문서작성/기존CLI 운용, 비작성자 문서 L4만 적용(L2생략, 새제품코드0). 각 역할 새1500초/closing180/검토최대2/no5. 기존 동일계열 비작성자 폴백 승인과 공통편향을 유지한다. 원141 clock/리뷰 기회를 되살리지 않는다. 실제USB 전에 정확2source/입력/argv L4를 받으며 판독 결과는 Root가 해당 계약과 대조해 별도 실행 증거로 남긴다.

AC1 관측된 두 슬롯/주소/flags·원파티션 checksum에 결속. AC2 read-only 2x4KiB/각45초/재시도0/실패중단/NVS배제. AC3 USB리셋·호스트CAN0·앱CAN미관측·사용자보고무급전 구분. AC4 저장 메타데이터와현재실행/전체무결성 구분 및빈칸/형식실패보존. AC5 non-U 기존CAN-U-only 차단과실제J5설정미확인 유지. AC6 기존코드·141검토/초과clock 불변, 정확핀과범위·인계기록 보존.
