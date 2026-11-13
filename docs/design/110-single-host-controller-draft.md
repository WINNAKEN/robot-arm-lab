> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 110 초안 — OS 시각 변경 없이 Isaac PC 안에서 실행 감독

2026-11-03 KST. **설계 조사 초안 / L2·구현·원격 실행 미착수**다. 109의 닫힌 검토를 재개하거나 새 번호로 같은 clock mutator를 다시 발사하는 계획이 아니다. 109의 원소스·BLOCK·EXHAUSTED 원장과 충분 임계는 보존한다.

## 현재 막힘

- 109 마지막 코드 L4 R2는 BLOCK4/2, 2/2 종결이다. 실제5초 cap과 pending launch의 terminal 소유 문제가 남아 자동 OS 시각 변경은 실행하지 않았다.
- 별도 읽기 전용 READY/challenge에서 현재 원격−로컬 구간은 `[5.2727070789, 5.2999540825]`초였다. 전체가 원108 ±1초 밖이므로 원108의 native 예산도 활성화하지 않았다. 이 자료는108 admission certificate나 표준 UTC 인증이 아니다.
- 108의 source/harness31개와 L4 PASS9/0·게인64/16/cap·097후보·정지/42초 기준은 그대로다. native45는 시작되지 않았다.

## 새 구조 후보

현재 로컬 PC에서 하는 실행 감독과 budget/clock 인증을 Isaac PC로 옮기고, 그 PC의 로컬 하위 프로세스로 SDK 작업을 실행한다. 감독자와 SDK가 같은 Windows wall/monotonic 시간축을 공유하게 한다. 로컬 PC는 승인된 패키지 전송과 상태·원자료 회수만 담당한다.

OS clock setter·UAC·시간서비스/NTP·네트워크/방화벽/VPN·바인딩 변경을 없애는 것이 목표다. ±1초 admission·0.25초 wall/monotonic jump·age120초·2700초 총예산·원 headroom/watchdog/회수 한도는 낮추지 않는다. 게인·cap·물성·프로그램·정지/운동 수용 기준도 바꾸지 않는다. 실제 같은 호스트에서 원 gate가 성립하는지는 구현/검수/실행으로 확인해야 하며 현재 통과로 간주하지 않는다.

## 직접 읽은 변경 접점

원108 `driver.py`의 `clock_argv`는 SSH로 OS 시각 producer를 호출한다. `remote`는 PowerShell 요청을 SSH로 전달하고, 회수와 dispatch에는 SCP가 있다. 새 구조에서는 이 경로의 로컬 프로세스/로컬 파일 전송 의미를 명시해 검토해야 한다. 단순히 PATH의 ssh를 바꾸거나 원코드 hash만 유지한 shim을 끼우지 않는다.

원108을 덮어쓰지 않고 새 namespace·입출력 경로를 사용한다. controller의 원자료 폴더와 SDK worker 폴더는 같은 PC에서도 분리해 기존 snapshot/exit/recovery provenance가 흐려지지 않게 한다. ZIP/manifest/실행 bytes 검증은 전송 방식이 달라졌다는 이유로 생략하지 않는다.

아직 다음 사항은 미확정이다.

1. 원108 source18/harness13·model/ref/설치 증거 중 controller 실행에 필요한 정확한 의존 파일 census와 패키지 크기.
2. remote controller의 source validation/activation/단일 소비·첫 원격 요청부터 예산이 시작되는 bootstrap ticket. 업로드·회수 시간을 예산 밖으로 숨길 수 없다.
3. local-process clock producer·SDK launch·회수 경로의 실제 caller별 불변 조건. 직접 파일 복사로 원 원자료를 덮어쓰거나 회수 성공을 가정할 수 없다.
4. client 연결 손실/remote controller 사망/자식 프로세스·로그 I/O 실패에서도 실제 terminal과 UNKNOWN을 구분하는 감독 구조. 109의 잘못된 pending/terminal shortcut을 재사용하지 않는다.
5. L급 변경이면 S/M 소유 단위로 분할한 새 L1/L2 및 전체 비작성자 L4 예산. 109의 L4 R3 또는 소진 계보 초기화로 처리하지 않는다.

이는 후속 L1의 조사 입력이다. source 구현이나 새 원격45분 실행 승인으로 쓰지 않는다. 계획과 실제 변경 census·검토가 구체화되기 전에는 설치·SDK/native·실물CAN·급전·flash·모터·물리 보정을 실행하지 않는다.
