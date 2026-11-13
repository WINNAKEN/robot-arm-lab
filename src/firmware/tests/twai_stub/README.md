# TWAI SDK stub 시험

실제 `components/robot_twai/idf_twai_port.cpp`를 별도 가짜 SDK 헤더/API와 함께 C++17로 빌드한다. `include/`는 이 시험 executable에만 추가한다. target IDF 빌드에는 포함하지 않는다.

`stub_sdk.cpp`는 호출 순서, zero-wait, config, 송수신 값, API 실패 및 stop 전후 늦은 상태 변화를 주입한다. 실제 ESP-IDF 드라이버/ISR/HAL의 실행 모형이나 실제 CAN 통신 시험은 아니다. pinned SDK compile/link가 별도로 필요하다. source 근거는 `_research/twai-adapter-evidence-20261023.md`다.

소스: `test_twai_port.cpp`, `stub_sdk.cpp`, production `idf_twai_port.cpp`.
Include: 이 폴더의 `include`, 이 폴더, `components/robot_twai/include`, `components/robot_can/include`.
각 테스트는 관측 가능한 API 인자/순서/결과를 단언한다. ctor/dtor는 I/O를 하지 않으며 사용자는 명시적 `close()`를 호출해야 한다.

프로젝트 루트에서 `pwsh -NoProfile -File src/firmware/tests/twai_stub/run.ps1`로 재현한다. 프로젝트 전용 Zig를 사용하며 `.dev/esp32-can-evidence/build/twai_stub/`에 compile.txt, run.txt, result.json(명령·소스 해시·실행 파일 해시)을 저장한다. 컴파일러가 캐시 rename 때문에 sandbox에서 실패하면 정식 권한 재시도를 사용하며 해당 실패를 시험 성공으로 취급하지 않는다.

close 결과의 `healthy`는 SDK의 최종 관측 가능한 SW 증거다. public stop이 아직 ISR에 반영되지 않은 HW interrupt를 지울 수 있으므로, 물리적/원자적 전체 버스 이력 보장으로 해석하지 않는다.
