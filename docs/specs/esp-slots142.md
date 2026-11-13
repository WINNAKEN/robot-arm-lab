# ESP 저장 슬롯 확인 / J5 준비 상태

2026-11-12 KST. COM7 USB 수신은 약8초 동안0B였고 정상 close됐다. ROM 파티션 read는 성공하여 ESP32-S3 revision0.2와 두 OTA 앱 파티션을 관측했다. 이 확인은 보드 리비전이나 실행 앱·CAN 통신 합격을 뜻하지 않는다.

| 저장칸 | 관측된 주소 | 전체 할당 크기 | 이번 읽기 |
|---|---:|---:|---:|
| app0 / ota_0 |0x10000|3MiB|앞4KiB 1회|
| app1 / ota_1 |0x310000|3MiB|앞4KiB 1회|

둘 중 어느 것이 실행 중인지 선택하지 않고 각각의 저장 헤더만 판독한다. 데이터가FF거나 app descriptor가 유효하지 않으면 그 사실을 남긴다. 전체 이미지·부팅 선택·제어 동작을 인증하지 않는다. NVS·otadata·전체 flash는 읽지 않는다. 각read는기존esptool의no-stub/read_flash/45초외부상한/단일연결시도이며재시도하지않는다. flash·RAM stub·보안설정은쓰지않지만USB ROM요청과리셋은발생한다. 모터무급전은사용자보고이며ESP자체CAN활동은NOT_MONITORED다.

J5는CAN형,ESP는U없는ESP32-S3-RS485-CAN으로사용자확인됐다. 기존진단은CAN-U만허용하여현보드에서BLOCKED_BOARD_ENUM_MISMATCH이고기본CAN비활성이다. 현재ID/CanRate·GPIO관측·HW/FW·모터정격/Ma·PSU V/A·퓨즈/차단/고정·120Ω실물대조는대기다. 새플래시·모터급전·CAN실조회·enable/정지/이동/교정은이번확인에포함하지않는다. 시험준비도구는src/bench/j5_can141.py plan이며후보ID1/2에서도오프라인읽기프레임4개만표시한다. 실제설정승인이나송신은없다.

정본결과는outputs/esp-stored-slot-142/Root-result.json과Root-summary.md에저장한다. 이전141의초과시간과미충족마감여유는변경하지않으며141전체절차를무조건PASS로표현하지않는다.141소스L4통과/새USB실행/실제모터시험은별도층위다.
