> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 087B — 남은 시간 안에서 비활성 ESP32 타깃 빌드 확인

087 HOST72/849·3변형·독립L4R1 PASS 뒤 추가할 검증이다. 사용자 요청의 ‘모듈 없이 가능한 검증’ 범위에서 이미 설치된 ESP-IDF5.5.6/도구만 이용해 독립 비활성 프로젝트를 컴파일/링크한다. 기존087 계획·HOST판정·source-freeze는 수정하지 않는다. 공통 종료14:23:28UTC, L2추가1회(R2)/L4추가1회(R2) 이내, 신규설치·업데이트·flash·port접속·실물급전·ISAAC접속 없음.

소유추가는 `.dev/can-readonly-evidence/build-target.ps1` 및 같은evidence의 독립target-build/·결과자료와 본계획뿐이다. 제품소스/기존SDK/기존빌드/기존활성app은 변경하지 않는다. 기존activate.ps1을 읽어 환경만 설정하고 SDK commit·소스무변경·도구버전전제를 확인한다. 자동설치 setup.ps1은 실행하지 않는다. dependency manager를끄고 네트워크패키지추가없이 빌드한다. sdkconfig는target-build 하위에만 생성한다.

출력은 ELF/BIN/map·실제build명령/exit/log·버전·원소스동결대조·해시다. 실제진단component/codec/TWAI/main이빌드된compile_commands와CMakeCache 경로를 확인한다. 기본main의DISABLED·승인false소스가입력과일치해야하며 기본app을대체하지않는다. 이것은타깃컴파일수용이며 실제CAN/RTOS지연/하드웨어수용이아니다.

한 번 빌드하며 프로세스 트리를 가진 숨김 실행의 상한360초/전체종료보다120초이상앞선시각으로둔다. 상한이면 자신이시작한빌드만종료/회수하고FAILED/TIMEOUT으로남기며 자동재시도·소스수리·target빌드기준완화없음. 통과여부와무관하게최종L4R2에서 실행경계·출력/원소스대조를확인한다. 이보완을시간내마치지못하면087HOSTPASS는보존하고실제타깃빌드는미완료로보고한다.
