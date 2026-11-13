"""Write self-contained import instructions, without pretending import ran."""
import json
from pathlib import Path


def write_readme(package):
    from build import write_json
    package = Path(package)
    cfg = json.loads((package / 'assumptions.json').read_text(encoding='utf-8'))
    rows = '\n'.join(f"| {r['link']} | {r['mass_kg']:.2f} | " + ', '.join(f'{v:.5f}' for v in r['com_m']) + ' | ' + ', '.join(f'{v:.6g}' for v in r['inertia_kg_m2']) + ' |' for r in cfg['links'])
    joints = '\n'.join(f"| {r['joint']} | 0 | {r['pose_deg']} |" for r in cfg['joints'])
    text = f'''# 우리 로봇암 v2 URDF 초안 — 시뮬레이션 가정 모델

`robot_arm.urdf`와 `meshes/`를 함께 복사합니다. 패키지의 STL 좌표는 **m**이며 URDF scale은 **1**입니다. 최신 전체 외장 v2 native CAD에서 새로 export한 31개 바디를 7개 링크·6개 회전 관절로 나눴습니다. 별도 J2 분할품/사이클로이드 시제품의 확정 물성이 적용된 것은 아닙니다. 원본 CAD·펌웨어는 수정하지 않았습니다.

상태: **URDF_DRAFT_STATIC_VALIDATED / ISAAC_IMPORT_NOT_RUN / RL_NOT_RUN**. 실제 Isaac 변환·중력/접촉·구동기 시험·학습·실물 보정/모터 운전은 하지 않았습니다. `validation.json`의 PASS는 파일·좌표 대조이며 물리 모델 정확도나 가져오기 성공을 뜻하지 않습니다. 링 치형·형상 검증은 계속 보류입니다.

## 0 자세와 각도

**URDF q=0은 preview.png/CAD의 현재 표시 자세**입니다. 관절 값은 출력축 canonical delta rad, 양의 방향은 오른손 규칙입니다. `q_geometric = q_urdf + radians(표시각)`이며 실물 영점/모터 영점은 미확정입니다. 6축모터는 미래 구성이고 CAN ID·모터 부호·encoder scale·실측 감속비는 채우지 않았습니다.

| 관절 | URDF 시작값 rad | CAD 표시의 기하각 deg |
|---|---:|---:|
{joints}

관절 제한 ±170°는 CAD 예시값이며 기계 한계가 아닙니다. 속도 0.5rad/s, effort [3,6,5,2,2,1]Nm, damping 0.05, friction 0은 임시 시뮬레이션 값입니다. MKS 모터 정격·가반하중·감속기 출력 토크로 사용하지 않습니다.

## 물성 가정 — 전부 미측정

질량은 초기 실험용 임의값입니다. 외장 CAD가 속이 찬 덩어리이므로 PLA 밀도×CAD 체적으로 실제 질량을 추정하지 않았습니다. COM은 각 링크의 로컬 외접상자 중심, 관성은 해당 질량의 균일 직육면체 근사입니다. 행렬 비대각 성분은 0입니다. 실제 모터·드라이브·베어링·프린트 외피/인필 분포와 구동부 반사관성·유격·마찰은 추후 대체해야 합니다.

| 링크 | 가정 질량 kg | 가정 COM xyz m | 가정 Ixx,Iyy,Izz kg·m² |
|---|---:|---|---|
{rows}

`assumptions.json`이 값·가정·미정 상태의 정본입니다. collision은 링크별 상자 1개로 단순화하여 실제보다 먼저 접촉할 수 있습니다. 자체 충돌과 작업공간 안전은 검증하지 않았습니다. 그리퍼는 없으며 말단 링크는 Link6입니다. 형상상 앞면 후보는 Link6의 +X32mm이며 보정된 TCP가 아닙니다.

## Isaac Sim 가져오기 순서 — 아직 미실행

1. 설치된 Isaac Sim 버전을 먼저 확인하고 그 버전의 URDF importer를 엽니다. 이 폴더 전체를 옮긴 뒤 `robot_arm.urdf`를 선택합니다.
2. 단위/스케일은 metre/1, 베이스는 fixed-base로 설정합니다. 초기 자체 충돌은 끄고, URDF의 질량·관성이 유지됐는지 가져온 값과 가정표를 대조합니다. 상자 충돌은 물리 검증 전까지 임시입니다.
3. 별도 USD 출력 위치로 변환합니다. 이 패키지에는 아직 USD가 없습니다. 시뮬레이션을 정지한 채 7개 링크/6개 revolute·연결 순서·표시0 자세를 preview와 비교합니다.
4. 관절 제어/drive를 별도 설정한 뒤 작은 시뮬레이션 각도에서 축과 부호를 확인합니다. 가져오기만으로 튜닝된 actuator가 생긴다고 가정하지 않습니다. 지면·작업대·접촉·질량·관성을 검증한 뒤에 중력/구동 시험을 진행합니다.
5. 학습은 다음 단계에서 Isaac Lab의 목표점 도달 과제부터 정의합니다. 관측·행동·보상·reset·종료조건·난수화가 필요합니다. 학습 결과를 CAN/실물 모터에 자동 연결하지 않습니다.

메뉴/옵션/API는 버전에 따라 다릅니다. `isaac_import_settings.json`은 권장값 안내이며 실행 가능한 Isaac API 인자파일이 아닙니다. 이번 작업에서는 시뮬레이터 설치·실행이나 importer 성공을 확인하지 않았습니다.

공식 문서 확인일 2026-10-27:
- [NVIDIA Isaac Sim URDF 가져오기](https://docs.isaacsim.omniverse.nvidia.com/latest/importer_exporter/import_urdf.html)
- [Isaac Lab 새 자산 가져오기](https://isaac-sim.github.io/IsaacLab/main/source/how-to/import_new_asset.html)

## 파일과 재현

`provenance.json`: 원본 native/3MF·기구학·승인된 math source·변환 CLI·가정 설정의 해시. 현재 SolidCraft export CLI는 0.23.0이며 예전 0.20.0 solver 검증을 새 버전 검증으로 확대하지 않습니다. `manifest.json`: 생성 파일 목록/해시. `preview.png`: 실제 생성 URDF/STL을 읽어 소프트웨어 렌더링한 표시0 자세.

저장소에서 재검사는 `py src/simulation/urdf_draft/verify.py models/robot-arm-urdf-v1`입니다. builder는 기존 출력폴더를 덮어쓰지 않습니다. 재생성 시 새로운 출력 경로를 지정하고 `.dev/urdf-draft-evidence/build-status.json`의 최신 시도 결과를 확인합니다. 부분 생성/실패 상태를 가져오기 완료로 취급하지 않습니다. 독립 검토 수용 범위는 저장소 `.dev/urdf-draft-evidence/disposition.md`가 정본입니다.
'''
    (package / 'README.md').write_text(text, encoding='utf-8', newline='\n')
    write_json(package / 'isaac_import_settings.json', {'status': 'GUIDANCE_ONLY_NOT_EXECUTABLE_API_CONFIG', 'import_tested': False,
        'fixed_base': True, 'asset_length_unit': 'metre', 'mesh_scale': 1, 'self_collision_initial': False,
        'keep_explicit_mass_inertia': True, 'joint_count': 6, 'joint_zero': 'CAD_DISPLAY_POSE',
        'initial_physics_state': 'STOPPED_UNTIL_IMPORT_AND_ACTUATOR_CHECKS',
        'actuator_gains': 'UNSET_TO_BE_CONFIGURED_AND_TESTED_IN_SIMULATION',
        'physical_hardware_approved': False, 'source_docs_checked': '2026-10-27'})
