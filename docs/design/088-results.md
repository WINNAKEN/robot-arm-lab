> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 088 — 읽기 진단 프로필·ESP32 실행 주기 준비 결과

2026-10-30. **오프라인 준비·HOST 시험·비활성 ESP32 타깃 컴파일 수용 완료**다. 실물 CAN 통신·플래시·급전·보정·모터 운전은 수행하지 않았다. 실제 RTOS 지터와 CAN 선로 응답은 NOT_RUN이다.

## 구현한 동작

- [프로필 기록 틀](../specs/read-diagnostic-profile.template.json)에 예상 제약과 실제 관측값을 분리했다. 보드·프로토콜·HW/FW·ID·bitrate·핀·배선/종단·전원 시 자동동작 배제는 실제 확인 전까지 미확인이다.
- `prepare_profile()`은 누락(Pending)과 불일치(Mismatch)를 구분하고 항목별 bit를 반환한다. 전부 일치한 ReadyForReview도 물리 승인이 아니며, 생성한 `Profile.hardware_approved`는 항상 false다. 기록 JSON을 펌웨어 실행 설정으로 읽지 않는다.
- 독립 진단 프로젝트는 FreeRTOS 1000Hz와 양수인 1ms tick을 정적으로 검사한다. 준비된 실행 경로는 `xTaskDelayUntil`로 1tick 절대 주기를 기다린다. 늦어서 대기하지 못하면 catch-up 반복 없이 종료한다.
- 공유 Cadence/Runner 경로는 관측 시각당 최대 한 번 poll한다. 같은 시각·이른 호출은 추가 poll이 없고, 역행·직전 서비스부터 10ms 이상·대기 실패는 Schedule 오류로 닫는다. 종료 뒤 helper의 포트/시계 I/O는 없다.
- 기존 ID1/2 단일 선택축의 `3A → F1 → 31 → 32` 읽기만 유지했다. Schedule 종료는 포트를 닫으며 토크/정지 명령을 새로 송신하지 않는다. 기존 응답·시간 기준은 완화하지 않았다.

상세 동작과 장치 수령 후 확인 순서는 [사용 문서](../specs/read-diagnostic-profile-and-period.md)를 따른다. 주문 화면은 CAN-U이나 모터 몸체의 `SERVO42D_485` 라벨만으로 부착 드라이브의 실제 통신 방식을 판정하지 않는다.

## 실행·검토 증거

| 구분 | 결과 | 원자료 |
|---|---|---|
| 작성자 HOST | 104시나리오 / 973검사 PASS, 변형 5개 모두 검출 | `.dev/can-read-profile-evidence/build/author-r1/` |
| 비작성자 HOST | 104시나리오 / 973검사 PASS, 변형 5개 모두 검출 | `build/reviewer-r1/` |
| 실제 main + SDK 선언 스텁 | 작성자·비작성자 PASS, 하드웨어·스케줄러 호출 0, 구성 승인값 무시 | `entry-stub-author-r2/`, `entry-stub-reviewer-r1/` |
| 음성 컴파일 대조 | 100Hz·0tick 각각 의도한 static_assert로 거절 | 각 스텁의 `result.json`·컴파일 로그 |
| 실제 ESP-IDF 빌드 | 1회, exit0, timeout 없음, 경고0, 실제 설정 1000Hz | `target-build/result.json` |
| L2 R1 / L4 R1 | 각각 MET9 / UNMET0, L4 발견 결함0 | `L2-r1.json`, `L4-r1.json` |

실제 빌드는 기존 ESP-IDF5.5.6(commit `880a203ae603d08a94d06aa01e0d6761958e5e9e`)와 기존 Xtensa14.2.0/Python3.12.10을 사용했다. 14:48:38~14:50:45UTC 실행, 전용 sdkconfig/build 디렉터리를 사용했다. 진단 main·diagnostic·codec·TWAI 컴파일을 확인했고 일반 운전 main은 포함하지 않았다. 새 설치나 flash/port 명령은 실행하지 않았다.

ELF 3,165,400byte / BIN 163,488byte를 생성했다. 소스13개·기존 입력5개 동결 핀과 타깃 산출물7개 hash/size를 작성자 및 비작성자가 대조했다. 세부 SHA는 `source-freeze-r1.json`과 `target-build/result.json`에 있다. 일반 운전 main/core/CanPort/TWAI, 웹/CAD/URDF/BOM은 이번 변경으로 수정하지 않았다.

## 실패 계보와 검증 한계

첫 스텁 음성 컴파일은 Zig의 syntax-only/unused `-c` 경고가 나와 기대한 정적 단언의 검출로 인정하지 않았다. 실패 로그 `entry-stub/tick100-compile.txt`를 보존했고, 실제 object 컴파일로 시험 관측부를 수정한 별도 `entry-stub-author-r2/`에서 두 정적 단언 거절을 확인했다. 기존 실패를 성공으로 덮지 않았다. 087의 100Hz 빌드·원자료도 보존한다(소스 기준 commit `12d77f3`).

타깃은 immutable false 및 미승인 프로필로 비활성이다. 컴파일의 1000Hz는 실물의 1ms 서비스 보장이 아니다. 실제 RTOS/ISR 지연·CAN 오류/응답·전원 시 동작·물리 정지/무토크 수용은 미검증이다. SDK wrapper의 강제 timeout/프로세스 종료 실패 주입도 NOT_RUN이다. 독립 검토는 같은 계열 비작성자 폴백이므로 공통 편향을 잔여 위험으로 기록한다.

모듈 도착 후에는 기존 수령 체크리스트로 현품·드라이브 통신 방식·HW/FW·단자·ID·bitrate·배선/종단·전원 시 동작을 확인해 관측 기록을 채운다. 이번 결과는 플래시나 실제 읽기 송신 허가를 만들지 않는다. Isaac 노트북 재접속·보정·모터 운전·링 형상 작업은 진행하지 않았다.

승인 단위는 14:33:36~15:18:36UTC의 45분, L2/L4 각 최대2회와 타깃 빌드1회였다. 실제 L2/L4 각1회·타깃1회를 사용했다. 새 실행 단위나 재빌드는 자동 시작하지 않았다.
