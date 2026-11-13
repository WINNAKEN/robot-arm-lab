# 068 정적 변환·검증 보조 코드

`models/robot-arm-urdf-v3/robot_arm.urdf`가 직접 작성한 정본이다. 이 폴더는 XML을 생성하지 않는다.

- `assets.py`: 원CAD 읽기/부품군 F/A/B/R 분리/메시 변환/실저장 box 계산/해시. 최초 준비 때만 실행하며 XML이 있으면 중단한다.
- `command.py`: 전체 손끝 간격(m) 하나를3개 물리joint 좌표에 대응한다. bool/NaN/무한대/범위 밖을 거절한다.
- `verify.py`: XML+실제 mesh를 원CAD 동작/독립FK/물성계산과 비교한다. 이전팔6joint+7link와 mesh는 바이트/구조 동일을 검사한다.
- `controls.py`: 동일 verifier를 통해20개 재봉인 음성 대조, 원본 전후 PASS와 해시 불변을 저장한다. 실행마다 고유 폴더를 만들어 기존 증거를 덮지 않는다.

기존 printforge venv의 numpy/trimesh/scipy/manifold3d를 읽기만 한다. `-I -B`로 실행하여 원CAD 경로에 bytecode를 쓰지 않는다. SDK/SSH/설치/하드웨어 동작을 포함하지 않는다. 069가 실제 Isaac 실행과 영상을 맡는다.
