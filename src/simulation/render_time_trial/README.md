# 076 — 렌더 시각 변환을 일치시킨 중력 전 구간 큰 동작

075의 정규화·tensor 게인64/16·영시간 초기화를 유지한다. 작업공간 점군은 실제 USD visibility=invisible이며 포그는 표시하지 않는다. 아래 점군 설명은 보존된 데이터 구조에 관한 것이다. 렌더 시각은 원 rational에서 float64 변환→1e9 곱→정수 절삭으로 검증하고, 실제 엔진 시각과 binary64 hex도 정확히 대조한다. 075 실패 실행은 보존하며 본 실행은 별도 원장을 사용한다. 076의 검토·HOST 수치는 outputs/isaac-render-time-v1의 원자료를 따른다.

별도 실험 소스다. 기존 latest_scene와 069~072 원본·실패·원장·검토는 보존한다. SDK lifecycle과 072의 실제 Base PhysX API 선언을 그대로 사용한다. 설치·실물·모터/CAN·학습 권한은 없다.

`program_for_purpose(source_program, purpose)`는 motion에서 원52초 프로그램을 복사하고, render_smoke에서는 같은 원본의 첫2초 hold 하나만 사용한다. 실제120 Hz와 영상10 fps를 구분한다. motion은6240물리스텝/521프레임, smoke는240스텝/21프레임이다. 모든 phase는 처음부터 중력 -Z9.81을 적용하며, 초기 reset 이후 q/qd 재설정과 중력 토글은 없다. 그리퍼 opening은40 mm 고정이다.

실제 9DOF 이름/열·11body/runtime질량·COM·관성·physics view와 시계를 기록한다. 매 명령 전 native gravity FF 전체열을 실제pose 기반 독립 합과 대조하고 원cap에서 abs(FF)를 뺀 drive cap만 사용한다. 유효 부하 초과나 추종 실패는 FAIL로 남기며 gain/cap을 올려 다시 실행하지 않는다. Kp64/Kd16과 물성은 모의 모델 가정이다.

고정seed7301/8192 샘플의 실제 feasible witness를25 mm voxel로 묶은 자료에서 최대1600개를 표시한다. native USD PointInstancer의 반지름10 mm 구와 opacity0.08 보라색 material이며 물리·충돌 API가 없다. 원 로봇은 실제 native 상태다. 점군은40 mm opening에서 샘플링된 가능 TCP 위치이며 연속·인증 작업공간이나 충돌 없는 경로를 뜻하지 않는다. cloud/계획 body bounds 합집합을 카메라 시야15%여유로 담고 수평·수직 aperture를 모두 명시한다.

native Replicator 출력의 actual RGBA8 바이트를 표준 PNG filter0/zlib1/CRC로 저장한다. software 재그림이나 replay는 없다. sidecar는 원 RGBA SHA와 PNG SHA·물리 상태·원 render product·실제 세 OG node의 compute generation·rational reference time을 묶는다. wrapper module/class/callable capability는 첫 프레임 전에 capture-api.json에 남긴다. 렌더가 물리 시계를 움직이거나 오래된 세대/blank/실패 로그를 내면 실패한다.

매 물리 row는 motion.ndjson에 append/flush한다. 진행 파일은 마지막 row/카운터/작은 checkpoint만 기록하고, 전체 report는 끝에 한 번 쓴다. Native 실행 예약·smoke 수용·motion 허가·독립 검증·MP4/Drive는 상위 driver가 관리한다. HOST24 PASS는 native physics/RTX 또는 L4 PASS가 아니다.
