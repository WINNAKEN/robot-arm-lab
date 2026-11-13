# KG1 벌림이 있는 MP9 최신 전체 팔 URDF

정본은 직접 작성한 `robot_arm.urdf`다. MP9 rev1 전체 외장 v3+KG1(FLAT)을 사용한다. MP10 J5는 목 결정이 완료되었지만 MP9 전체 조립에 통합되지 않은 단독 부품이므로 포함하지 않는다. 이전 v1/v2 URDF와 CAD는 수정하지 않았다.

- 12링크: 물리11 + 질량/형상 없는 tool0. 팔6 revolute + 그리퍼2 prismatic/1 revolute = 물리9 movable, 독립7좌표.
- q=0은 기존 표시 자세, KG1 한쪽 u20mm/전체40mm 벌림이다. 실물 영점이 아니다.
- G원점은 Link6+X28mm 플랜지, G+X=Link6+Y, G+Y=Link6+Z, G+Z=Link6+X. tool0은 G+Z103mm의 명목 중앙점이며 보정된 TCP가 아니다.
- 47그리퍼 부품은 F23/A6/B6/R12로 한 번씩만 들어간다. KG1에는 고정 F만, KG1_A/B에는 턱/패드/나사, KG1_R에는 피니언/혼/스플라인/나사가 있다.

하나의 논리 명령 `opening_m`는 접촉면 사이 전체 간격0..0.094m다. `src/simulation/gripper_urdf/command.py::joint_positions(opening_m)`로 물리joint 값을 얻는다. d=opening_m/2−0.020m이며 다음 값은 URDF joint 영점에서의 변위다.

| joint | 물리값 | limit | 양의 방향 |
|---|---|---|---|
| KG1_slide_A | d | −.020..+.027m | G−X로 열림 |
| KG1_slide_B | d (mimic A×1+0) | −.020..+.027m | G+X로 열림 |
| KG1_pinion | −d/.0135 (mimic A×−74.07407407407408+0) | −2..1.4814814814814814rad | G+Y 오른손 회전 |

피니언 zero origin=(0,0,.026)m, zero pitch=−20/13.5rad이다. mesh는 닫힌 CAD를 중심축으로 옮겼고 joint origin에서만 u20 각을 준다. 전체 CAD 각은 −opening_m/(2×.0135)rad이다. 표준 URDF mimic은 affine 관계이며 동적 치면 접촉을 뜻하지 않는다. Isaac importer가 이를 어떻게 가져오는지는 069의 실제 결과에서 따로 기록한다.

물성은 가정이다. 기존 그리퍼184.2g을 F119.19363636/A24.64090909/B30.76090909/R9.60454545g으로 분할해 중복 없이 유지한다. 인쇄 질량은 기존 슬라이서 자료, 서보 스플라인.2g 분리와 나사9g 분배는 가정이다. 팔4.15kg, 총4.3342kg. COM/관성은 실제 저장 mesh AABB의 균일box, collision은 군별 AABB proxy다. 고정 관을 포함하는 F box가 턱 proxy와 겹칠 수 있어 selfcollision/접촉 수용을 주장하지 않는다. limit/effort/velocity/damping도 시뮬레이션 시작 가정이다.

068의 확인은 정적자료/기구학 범위다: cadgen0.8.2 strict 0issue, 원CAD/실제STL 20동작 자세 비교, 20재봉인 음성 거절, CAD Viewer 표시와 전 movable 한계 snapshot. SDK/물리/접촉/구동/학습/실기 수용은 이 결과에서 추론하지 않는다. 069 결과를 별도로 확인한다. 링 검증과 기존 EXH 이력은 그대로다.

재현(저장소 뿌리, 기존 printforge venv; 설치 없음):

```powershell
& C:/projects/printforge/.venv/Scripts/python.exe -I -B src/simulation/gripper_urdf/verify.py
& C:/projects/printforge/.venv/Scripts/python.exe -I -B src/simulation/gripper_urdf/controls.py
```

검증 원자료: `outputs/urdf-gripper-v3/verification.json`, `semantic-controls.json`, `snapshot-sweep.json`. `manifest.json`은 이 묶음의 바이트를 결속한다. source input94개 해시 정본은 provenance.json에 있다.
