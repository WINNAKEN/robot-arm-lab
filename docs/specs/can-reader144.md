# ESP 조회 전용 브리지144

> 배포 준비 당시의 사양 기록입니다. 이후145에서 앱 배포를 완료했고 J5 ID1/500K에서 속도 읽기1회가 성공했습니다. 최신 결과와 한계는 [STATUS](../STATUS.md)를 확인하세요. 아래 원시 배포/백업 경로는 공개본에 포함하지 않습니다.
사용자 보드 ESP32-S3-RS485-CAN(non-U), 모터 전원OFF·조립유지 상태에서 업로드한다. 부팅/INFO에는CAN driver가 설치되지 않고TX0이다. USB Serial/JTAG 115200으로 INFO를 보내면 앱/버전/IDF/ELF해시/boot_id/uptime_ms/info_seq/설치상태/송신시도수를 반환한다. 배포 확인은6초 관측·5회 이상 새INFO·같은boot_id·4초이상 증가하는uptime으로 제한된 부팅 안정성을 확인한다. 무한시간 안정성을 보장하지 않는다. 실제모터전원은 제어/계측하지 않는다.
미래 실제CanID/rate 확인 뒤 READ 1 500000 31 같은 명시적 요청을 보낼 수 있다. 현재 단위는 INFO만 사용하며 CAN READ0이다. ID1..16·bitrate125000/250000/500000/1000000·opcode31/32/F1/3A만 허용한다. generic/raw/scan/설정/enable/회전/CAL/홈 명령은 없다. F3 비활성 명령도 이 브리지에는 없다. READ는single-shot1회,수신250ms/32프레임 제한,TX대기25ms,항상stop/uninstall이다. 설치/정리실패는FAULT latch이며USB 재부팅전READ를거부한다.
GPIO15TX/16RX는제조사보드기대값이다. actual배선/ID/rate/HWFW 검증을 대신하지 않는다. READ normal세션에는controllerACK가생길수있다. 부팅/INFO의CAN비활성은모터드라이버자체의자동시작/초기움직임방지인터록이아니다.
실제16MiB 전체백업·동일장치검증 후 기존bootloader/partition/NVS를보존하고 app0/otadata만교체한다. 배포오류·readback오류·USBINFO실패면검증된원app0/otadata를같은보드로복원하고검증한다. backup은개인정보가능local-only자료다. 성공/실패는outputs/esp-readonly-flash-144/의실측기록을따른다. 모터CAN응답/실물정지/배선PASS는아직선언하지않는다.
