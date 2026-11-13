# Robot Arm Lab

3D 프린팅으로 만드는 소형 6축 로봇암의 기구 설계, Isaac Sim 시뮬레이션, ESP32·CAN 제어 개발 기록입니다. 성공한 결과와 아직 해결되지 않은 문제를 함께 공개합니다.

> **현재 실물 검증은 J5 한 축의 CAN 읽기 응답까지입니다.** 실제 관절 이동·비상정지·충돌 회피·물체 집기 성능은 검증하지 않았습니다. 현재 ESP에 배포한 `can_reader144`는 조회 전용입니다.

## 현재 상태

| 영역 | 확인한 내용 | 남은 내용 |
|---|---|---|
| 기구 | 자체 CAD 생성기, 감속기·손목·그리퍼 설계와 출력/끼움 기록 | 전체 실물 조립 대조, 강도·하중·공차 검증 |
| 로봇 모델 | MP18 기반 URDF v4, 메시·추정 질량·COM·관성 | 실측 물성, 전 자세의 충돌 없는 동작 범위 |
| 시뮬레이션 | 원격 Isaac 가져오기·토크/추종/종료 문제 조사와 수정 | 수정된 최신 집기 시나리오의 동역학 재검증 |
| ESP | ESP32-S3-RS485-CAN(non-U)에 조회 전용 앱144.1 배포·확인 | 제한된 이동·정지 경로의 별도 준비/검증 |
| 실제 CAN | 2026-11-12, J5로 연결한 ID1·500K에서 속도 조회 1회 정상 응답, 보고값0RPM | 실제 움직임, 축 방향·감속비·하드웨어 원점 보정 |
| 그리퍼 | Feetech STS3215 12V TTL 인터페이스 구분 | TTL 어댑터 연결 및 실물 제어 |

세부 판정은 [현재 검증 상태](docs/STATUS.md), 진행 과정은 [개발 일지](docs/development/JOURNAL.md)에 정리했습니다.

## 구조

```text
src/firmware/can_reader144/   실제 배포한 조회 전용 ESP-IDF 프로젝트
src/firmware/components/     제어·정지·소유권·CAN 등 장치 독립 코어와 준비 구현
src/firmware/tests/          기존 HOST·브라우저·어댑터 시험
src/bench/                   실물 준비 도구와 조회 브리지 HOST 시험
src/simulation/              Isaac 가져오기·관측·시나리오·수용 검사
src/cad/                     자체 CAD 생성기와 치수/끼움 원장
models/robot-arm-urdf-v4/     최신 공개 URDF와 시각/충돌 STL
models/                     이전 자체 모델의 텍스트 매개변수·설명·출처
docs/design/                당시 작성한 설계·결함 조사·검토 계획의 이력
docs/specs/                 CAN·배선·실험 준비 문서
docs/development/           공개 개발 일지
tools/                      공개 파일 검사와 파일 목록 생성
```

## 먼저 읽기

- [최신 검증 상태와 실물 시험 범위](docs/STATUS.md)
- [CAN 조회 전용 브리지](src/firmware/can_reader144/)
- [J5·J6 CAN / STS3215 TTL 배선 준비](docs/specs/j5-j6-can139.html)
- [URDF v4의 좌표·가정·한계](models/robot-arm-urdf-v4/README.md)
- [소스·문서 공개 범위와 재현 한계](docs/PUBLICATION.md)
- [외부 자료와 라이선스 출처](THIRD_PARTY_NOTICES.md)

## 장치 없이 확인하기

Python3.12와 C++17 컴파일러로 공개 트리의 형식·누락·금지 파일과 조회 브리지 로직을 검사할 수 있습니다. 이 명령은 USB·CAN·모터에 접근하지 않습니다.

```sh
python tools/check_public_release.py
c++ -std=c++17 -O2 src/bench/test_can_reader144.cpp -o /tmp/test_can_reader144
/tmp/test_can_reader144
```

Windows에서는 C++ 출력 경로를 로컬 임시 폴더의 `.exe`로 바꿔 사용합니다. 같은 검사를 위한 [CI 설정 예시](docs/ci/README.md)를 포함하지만, 초기 공개판에는 GitHub Actions 자동 실행을 활성화하지 않았습니다.

조회 전용 앱의 타깃 빌드에는 **ESP-IDF5.5.6**이 필요합니다. `src/firmware/can_reader144/`에서 `idf.py build`로 빌드할 수 있지만, 기존 보드의 flash 크기·파티션·펌웨어·전원 조건 확인 없이 임의로 flash하지 않습니다. 과거 통합 앱과 실제 배포한 조회 앱은 서로 다른 프로젝트입니다.

## 개발 기록을 읽는 방법

설계 문서의 번호는 시간에 따른 실험 단위입니다. 과거의 PASS는 그 문서에 적힌 범위의 결과이고, 최신 실물 운전 허가를 뜻하지 않습니다. 코드의 시험용 fake CAN·stub·시뮬레이션 결과와 실제 모터 시험을 구분합니다. 일부 과거 시험은 로컬 비공개 증거·외부 CAD·SDK 환경을 필요로 해 이 공개본만으로 재현되지 않습니다.

이 저장소는 원본 작업 트리에서 선별한 **새 공개 이력**으로 시작합니다. 개발 중의 전체 로컬 Git 객체·인증정보·장치 원본 덤프·외부 패키지·원시 실행 로그는 공개하지 않습니다. 앞으로 공개 변경과 중요한 실패/수정 내용을 함께 기록합니다.

## 재사용

현재 프로젝트 자체 코드·문서의 별도 오픈소스 라이선스는 선택하지 않았습니다. 공개 여부와 재사용 허가는 구분하며, 외부 자료에는 각 원저작자의 조건이 적용됩니다. [라이선스 및 출처](THIRD_PARTY_NOTICES.md)를 먼저 확인하세요.
