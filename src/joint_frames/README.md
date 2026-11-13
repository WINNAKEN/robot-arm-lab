# 021 관절 프레임 수학 후보

장치 없는 m/rad 수학 코어다. 입력은 v1 `kinematics.json` 한 파일이며
v2 native CAD 형상·관절 runtime 일치를 검증하지 않는다. 기존020은 동결 BLOCK이다.

저장소 루트에서:

```powershell
py src/joint_frames/test_frames.py
py src/joint_frames/run_checks.py
py src/joint_frames/frames.py build
py src/joint_frames/frames.py verify
```

결과는 `outputs/joint-frames-v1/runs/<run_id>/frames.json`이다.
`current.json`의 PASS는 생성 무결성만 뜻한다. 독립 검토 수용은 `.dev/joint-frames-evidence/`를 따른다.
동시 작성은 지원하지 않는다. 출력 경로는 고정하고 테스트는 임시 root를 사용한다.
기존 run을 수정하지 않고 새 run을 만들며 verify는 읽기만 한다. 입력/producer가 바뀌면 재생성한다.
성공 전 일반 예외는 finally에서 FAILED를 남기고 재전파한다. 저장 불가/강제 종료는 기록 보장 밖이다.
저장 자체가 불가능하면 과거 current가 남을 수 있다. 이 경우 build의 실패를 기준으로 중단하고 저장 복구 후 새로 생성한다.

`decode(bytes)`가 frozen Layout/Joint를 만들고, FK/변환 API는 이 검증된 타입만 받는다.
canonical 양수는 오른손 회전이며 native runtime 양의 angle과 대응은 미검증이다.
`q_geometric = q_delta + pose_rad`; delta0은 현재 표시 자세다.
변환/FK 입력은 유한 float 표현 범위이며 임의 ±1e6rad 제한을 두지 않는다.
이는 기계 가동범위가 아니다. 극대 각도는 표현 경계 회귀용이며 삼각함수의 물리 정확도를 보증하지 않는다.
변환 왕복은 부동소수점 오차 이내의 비교이며 비트 단위 가역성을 뜻하지 않는다.
기하학적0 자세에서 축 순서 Z/Y/Y/X/Y/X, 원점은 다음과 같다.

| 관절 | 원점 m | 표시각 deg |
|---|---|---|
| J1 | 0, 0, .096 | 15 |
| J2 | 0, 0, .174 | -50 |
| J3 | .165, 0, .174 | 70 |
| J4 | .305, 0, .174 | 15 |
| J5 | .383, 0, .174 | 25 |
| J6 | .523, 0, .174 | -10 |

위 표는 현재 원본의 읽기용 예시다. 실행 결과와 원본 해시가 정본이다.
모터 부호/CAN ID/감속비/실물 영점/한계/엔코더 스케일/관성/TCP는 미정.
링 indexed-geometry 증명은 미해결 보류이며020 반례를 폐쇄하지 않는다.
실물·펌웨어·CAD 변경·Isaac 설치/월드·강화학습은 수행하지 않는다.
