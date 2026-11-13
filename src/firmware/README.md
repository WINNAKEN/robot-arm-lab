# ESP32 펌웨어 준비 — ST3-D

> 아래는 과거 통합 펌웨어의 단계별 기록입니다. 현재 실제 배포 앱은 별도 `can_reader144/`의 조회 전용 앱144.1이며, 최신 실제 검증 범위는 [STATUS](../../docs/STATUS.md)에 정리했습니다. 이 폴더의 HOST/stub 결과를 실물 이동·정지 수용으로 해석하지 않습니다.

현재 ST3-D: 휴대폰 인증·요청·화면, 단일 Boot/Run/CAN 소유자와 실제 SDK HTTP/실행부를 연결했다. strict host3023·변형3개, HTTP stub2142, runtime stub904, UI34 및 기존 회귀 PASS. SDK 기본/준비 두 빌드 경고0, 실제 ELF 실행 경로·웹 바이트 일치, 독립L4R2 PASS9/0. 정본 `.dev/phone-runtime-evidence/disposition.md`. 기본 app 비활성·물리 승인false, 실제 Wi-Fi/CAN/모터·플래시·휴대폰 실측은 NOT_RUN이다. 아래 ST2~C 설명의 미완료/4초창은 해당 단계의 이력이다.

최신 ST3-C: 실제 항목별 설정 재조회로 증명을 갱신하며 고정4초 종료를 대체했다. Runtime28/1527570·변형5개와 Boot/Run 회귀, 독립L4R2 PASS9/0. 정본 .dev/runtime-refresh-evidence/disposition.md. 휴대폰/ESP32 연결과 타깃빌드는 다음D이며 기본장치미승인/비활성 유지. 아래4초창은 이전 이력이다.

최신 ST3-B: robot_boot의 읽기 전용 부팅 확인과 명시적 유지보수·전체해제/heartbeat설정·선택축허가·동일포트 Run 인계를 호스트에서 검증했다. Boot46/7302·변형3개, 기존Run51/3426·변형2개, 독립L4R2 PASS8/0. 정본 `.dev/boot-torque-evidence/disposition.md`. 현재 인계된 설정증명의 남은≤4초 시험창이며 장시간 Run 설정재조회·휴대폰인증어댑터·app연결·신규ESP32빌드/실물은 미완료다. 아래 ST3-2의 부팅미구현 설명은 이전 이력이다.

최신 ST3-2: `components/robot_run/`의 정상 CAN 벤치 경로와 StopLink 인계를 호스트에서 검증했다. 기본 승인false인 post-maintenance/already-enabled fixture 전제이며 전체 부팅/F3 허가 절차가 아니다. 정상 송신 단일 소유자·실제 TX 완료·FD 시작/완료·새 위치/속도/enable 증명 후 완료, 정지 시 일반 송신 폐기와 기존 StopLink의 실제 reset/검증/close를 연결한다. strict C++17 시험51시나리오/3426단언·변형2개 검출, 최종 독립L4R2 PASS. 현재 정본 판정은 `.dev/normal-can-evidence/disposition.md`. app_main·기존 컴포넌트는 불변이며 신규 target rebuild·웹·실물은 NOT_RUN이다.

후속 ST3-1의 독립 컴포넌트 `components/robot_gate/`를 추가했다. 2축 typed 요청의 세션·800ms 제어권·500ms 단발 이동표·중복/만료 거절·정지 우선순위를 장치 없이 검증한다. `tests/gate/run.ps1 -Mutations`의 strict C++17 호스트 시험은43시나리오/269단언, 회귀 변형2개 검출이다. 검토 처분은 `.dev/control-gate-evidence/`를 따른다. app_main·CAN/웹·SDK에는 연결하지 않았으며 이 컴포넌트의 ESP32 target rebuild와 실물 시험은 NOT_RUN이다. 아래 ST2 실행 경계와 기존 소스는 보존한다.

현재 구현은 **C++ CAN codec·정지 코어, CAN 연결 조정기, 실제 ESP-IDF TWAI 연결부**다. 기본 실행 진입점은 driver를 시작하지 않는다. 휴대폰 화면은 `docs/design/mockups/phone-control-preview.html`의 모의 화면이며 보드에 연결되지 않았다. 정지 시간 계약은 `docs/design/007-stop-timing-and-firmware-preparation.md`, 연결부 계약은 `008-esp32-build-and-can-adapter.md`다. 이전004/006/PDF의100ms·1600ms 정지 시간은 구현 기준으로 사용하지 않는다. 최신 빌드·시험·검토 판정은 `.dev/esp32-can-evidence/validation.md`를 확인한다.

## 정지 시간 수정

| 단계 | 이번 기준 |
|---|---|
| 기존 송신 격리 | 최초 정지 요청부터100ms 미만 |
| F7 정지 명령·응답 | 격리 포함600ms 미만, 축당1회 |
| 무송신 감시 | 마지막 확인TX부터1300ms |
| 위치·정지·속도·enable 진단 | 감시 종료부터1700ms 미만 |
| 전체 확인 상한 | 최초 요청부터3600ms 미만 |

위 시간은 **정지 확인 절차의 시간**이다. 기계가3.6초 안에 멈춘다는 보증이나 실제 비상정지 회로의 응답 시간이 아니다. F7는 먼저 시도하고 뒤에서 정지 여부를 확인한다. 반복 정지 요청은 시간을 연장하지 않는다. 확인 실패는 `Fault`, 확인 성공도 재허가가 필요한 `StoppedRecheck`다.

진단은 `[위치31 → 운전F1 → 속도32 → enable3A]` 순서에서 각축을 조회하고3회 반복한다. 한 슬롯60ms, 동일축 위치는1축240ms/2축480ms 간격이다. 마지막회전 관측 age는700ms 미만이며 평상시400ms stale 기준과 별개다. 초기 두 위치는 안정성 판정 이력이다.

## 파일과 경계

- `components/robot_core/mks_codec.cpp`: ID1/2 rawCAN 인코딩·검증. signed48 위치, signed16 속도, 정해진 상태값만 허용한다.
- `components/robot_core/stop_coordinator.cpp`: 주입된 단조시계와 rawCAN/TX완료/격리결과를 처리한다. 정지 모듈은 F7와진단조회만 출력하며FD·F3를 출력하지 않는다.
- `tests/host/`: 위 production C++를 그대로 컴파일하는 Windows 호스트 시험과 이전 시간표 회귀 변형 시험.
- `components/robot_can/stop_link.cpp`: 단일 소유자·단일 TX, 실제 완료 알림과 응답 연결, RX 서비스 간격·오류·최종 종료 검사, 최근64개 raw 이벤트 로그.
- `components/robot_twai/idf_twai_port.cpp`: 실제 SDK v2 handle API. TX queue0/RX queue16, single-shot/zero-wait, 새 driver 수명, 종료 직전 관측 가능한 오류 보존.
- `tests/adapter/`, `tests/twai_stub/`: 실제 위 C++를 fake port/SDK stub에 연결해 실행한다. stub 성공은 실물 송수신 성공이 아니다.
- `main/app_main.cpp`: ESP32-S3/ESP-IDF5.5.6 확인, 연결 객체 생성 및 준비 로그만. 생성자에는 장치 I/O가 없으며 Wi-Fi/TWAI/웹/GPIO/모터 초기화를 호출하지 않는다. 하드웨어 승인 설정을 켜도 운전하지 않는다.

코어는 동적할당·파일·네트워크·시리얼·장치 API를 사용하지 않는다. `StopProfile`은 기본 미승인이다. 시험 fixture에서만 가짜 프로필을 승인한다. 실물 승인 값은 아직 없다.

## 호스트 시험 실행

프로젝트 루트에서, 준비된 프로젝트 전용 Zig0.17.0 도구를 사용한다. 도구 출처·해시는 `.dev/firmware-core-evidence/toolchain/README.md`에 있다. 전역PATH 설정은 필요 없다.

```powershell
& .\src\firmware\tests\host\run.ps1 -Mutations
& .\src\firmware\tests\adapter\run.ps1 -Mutations
& .\src\firmware\tests\twai_stub\run.ps1
```

`run.ps1`는 현재 PowerShell 프로세스의 캐시·임시경로를 프로젝트 내부로 설정한다. production 소스를 바꾸지 않고 `.dev/firmware-core-evidence/build/`의 복사본에서만1600ms 전체상한과100ms 동일코드 재조회 변형을 만든다. 원본은 성공, 두 변형은 시험 실패가 기대값이다. 일반 sandbox에서 컴파일 캐시 rename 오류가 발생한 이력이 있으며 실패 기록은보존한다. 도구 실행 환경을 고쳤다고 firmware 논리를 바꾸지 않는다.

ST1 결과는 `.dev/firmware-core-evidence/validation.md`, ST2 결과는 `.dev/esp32-can-evidence/validation.md`에 구분한다. adapter 변형은 종료 healthy 검사를 제거하거나 poll 간격10ms 경계를 허용하여 시험이 검출하는지 확인한다. 빌드 캐시에만 변형 사본을 만들며 원본 코드를 변경하지 않는다. ESP32 target빌드·플래시·실물정지·휴대폰통신은 호스트 시험 결과에 포함하지 않는다.

## ESP32-S3 실제 빌드

프로젝트 루트 PowerShell에서 다음을 실행한다. ESP-IDF와 도구는 `.dev/tools/esp-idf-local/`에 설치되어 있으며 전역 PATH·레지스트리·USB driver는 변경하지 않는다.

```powershell
. .dev/esp32-can-evidence/sdk/activate.ps1
& .dev/esp32-can-evidence/sdk/verify-environment.ps1
$buildDir = Join-Path (Get-Location) '.dev/esp32-can-evidence/sdk/st2-build'
$configFile = Join-Path (Get-Location) '.dev/esp32-can-evidence/sdk/st2-sdkconfig'
& $idfPython "$env:IDF_PATH/tools/idf.py" -C src/firmware -B $buildDir -D "SDKCONFIG=$configFile" build
```

출력은 해당 build 폴더의 `robot_arm_lab.elf`, `robot_arm_lab.bin`이며 출처·도구 버전·해시는 `.dev/esp32-can-evidence/sdk/`에 보존한다. SDK가 빌드 후 보여주는 flash 안내는 실행하지 않았다. 보드의 flash/PSRAM 구성 확인, 실제 업로드·부팅·통신은 별도 수용 대상이다.

ST2 실제 빌드는 성공했고 컴파일/CMake 경고는0건이다. TWAI shim과 실제 SDK 함수는 ELF에 포함됐다. 사용하지 않는 StopLink.begin_stop/poll·코어 실행 함수는 타깃 라이브러리에서 컴파일됐지만 최종 비활성 앱 ELF에서는 제거됐다. 전체 운전 actor를 붙인 뒤에는 그 실행 경로의 target link·runtime을 다시 검증해야 한다.

## supervisor에서 연결할 때의 계약

1. 한 supervisor가 코어를 소유하고 모든 입력을 직렬화한다. 외부는밀리초 단조시각을 전달한다. terminal인스턴스는재사용하지않고후속supervisor의명시적재점검후새인스턴스를만든다.
2. `take_action(now,out)`이성공한경우에만action을소비한다. 이함수도기한만료를먼저검사하고진단action출고는고정슬롯+10ms미만이어야한다. adapter는action의 `dispatch_before` 이전에즉시제출하며별도큐에쌓거나나중에재전송하지않는다. 반환false의out을사용하지않는다. `Isolate`는 기존 큐/송신/알림을 격리한 실제 결과로만 `on_isolated`에 보고한다. 격리 성공을 가정하지 않는다.
3. `Transmit`의token은 로컬TX완료용이다. CAN에싣지않는다. API접수만으로성공보고하지않고 실제TX완료를 `on_tx_result`에 알린다. 잘못된/옛token은Fault다. 종료 후의늦은사건은새운전으로이어지지않는다.
4. RX를dequeue한즉시시각을찍고 `on_frame(now,dequeued_at,frame)`에전달한다. 두시각은구분한다. 처리지연10ms이상은Fault이며, **처리시각now가기한에도달하면수신시각이빨랐어도거절**한다. 기한의성공이벤트가timeout을뒤집지않는다.
5. TX완료통지를RX보다먼저전달한다. 그전응답은성공으로승격하지않으며adapter는raw로그를보존한다. 코어자체에는로그저장소가없다. invalid프레임을유효상태나신선도표시로전환하지않는다.
6. Quiet동안다른task/keepalive/설정/조회가CAN송신을하지않도록adapter가독점권을보장해야한다. 코어가외부task의송신을감지하거나취소할수있는것은아니다. bus-off/RXoverflow는즉시보고한다.
7. CAN 응답에는요청nonce가없다. 유효수용창안에들어온오래된같은코드응답을완전히구별할수없다. 실제응답지연상한·heartbeat설정/readback·오차값의승인없이운전에연결하지않는다.

후속 supervisor는 `StopLink`를 한 task에서만 소유하고, 승인된 실물 프로필로 `begin_stop`한 뒤10ms 미만 간격으로 `poll`해야 한다. 한 poll의 처리도10ms 미만이다. 현재 기본 app은 이 두 함수를 호출하지 않는다. 기본 FreeRTOS tick 설정에서 `vTaskDelay(1)`이 이 간격을 만족한다고 가정하지 말고 actor 구현과 실제 부하 시험에서 정해야 한다. 직접 TWAI API를 호출하는 두 번째 task는 허용하지 않는다.

코어의 `StoppedRecheck`만 읽지 말고 **StopLink.state()**를 최종 결과로 사용한다. 마지막 오류·종료 실패·시간 초과 때문에 core가 terminal이어도 링크는 Fault일 수 있다. `close_result().quiesced`는 driver 제거, `healthy`는 제거 직전 관측 가능한 SW 상태다. 둘 다 참이어도 물리 차단·모터 정지·토크 해제 보증은 아니다.

SDK에는 hardware RX timestamp가 없다. dequeue 시각을 선로 도착 시각으로 표시하지 않는다. poll gap/RX backlog/overflow 검사와 송신 직전 알려진 잔여 RX 거절을 구현했지만, ISR 미보고 사건·임의 지연 replay·실물 응답 지연 상한을 소프트웨어 시험만으로 입증하지 못한다. `StopProfile`의 실제 승인 값은 모두 미확정이다.

CAN부품은 Waveshare CAN-U + MKS CAN MT, 후보 TX15/RX16/500k다. shim에 이 후보가 들어 있지만 기본 app은 설정을 장치에 적용하지 않는다. 실제보드통합전003배선가이드와수령한보드/FW를대조해야 한다.

## 남은 작업

- 부팅/프로필검증/운전허가/고정100펄스동작/토크해제 supervisor.
- SoftAP와HTTP/WS, 단일조작권·세션만료·재접속거절을휴대폰화면에연결.
- 실물별heartbeat·응답지연·정지오차·K1/퓨즈·전원·고정 확인과 H시험.

실제운전과구매는이번준비작업에포함하지않는다.
