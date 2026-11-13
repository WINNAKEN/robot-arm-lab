> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 소형 6축 로봇암 프로젝트 등록

날짜: 2026-10-22. 세션: 기획 robot-arm-lab #1.
프로젝트 식별자: `robot-arm-lab`. 이름: 소형 6축 로봇암 실험실.

## 배경

사용자가 받은 ZIP 4개와 한국어 시작 안내문을 바탕으로 독립 프로젝트를 등록한다.
제공 안내문의 정리일은 2026-10-21이다. 아래 내용은 그 자료의 계획을 접수한 기록이다.

## 제공 자료의 방향

- 1차: SweepDynamics Armold와 비슷한 규모의 소형 6축으로 통신·제어·기구 제작 학습.
- 먼저 MKS SERVO42D CAN 드라이버 2개로 시험. 보드만 구매할 경우 호환 NEMA17 모터 2개 필요.
- 2차: 1차 성공 뒤 RobStride 기반 확장 검토.
- 완성 장비의 하중·도달거리·감속비·모터 길이·성능은 미확정.
- Armold 전체 CAD 및 일부 유료 STEP/SolidWorks 자료는 미확보로 안내되어 있다.

## 선택지와 결정

기존 ROS2/물류 프로젝트에 편입하거나 별도의 실험실로 관리할 수 있다.
이번에는 받은 자료의 독립성과 MKS → RobStride 단계 구분을 보존하기 위해
`C:/projects/robot-arm-lab`에 새 로컬 프로젝트를 만든다.
이는 자료 등록 결정이며, 구현 계획 승인이나 구매 지시를 뜻하지 않는다.

## 자료 위치

- `../references/00_robot_arm_START_HERE_KO_20261021.txt`: 받은 시작 안내 원본.
- `../references/packages/01/`: Thor / SmallRobotArm / Faze4 / PAROL6.
- `../references/packages/02/`: B601-RS / EDULITE_A3 / RobStride 제품 자료.
- `../references/packages/03/`: Makerbase MKS CAN / Arctos 제어 참고.
- `../references/packages/04/`: AR4 무료 자료 / 유료 자료 구매 안내.
- `../references/INTAKE_MANIFEST.json`: ZIP 원본 경로·SHA-256·파일 수·CRC 검사.

## 남은 결정

후속 지시 전까지 대기한다. 구매 부품 확정, CAN 어댑터 선택, 시험 구성 설계,
실물 버전 확인, 구현 계획 및 독립 검수는 아직 착수하지 않았다.
