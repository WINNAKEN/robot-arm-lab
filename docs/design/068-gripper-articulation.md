> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 068 — 최신 MP9 KG1 벌림 관절 URDF

상태: L2 R1 PASS9/0 후 L3 구현/작성자 기계검사 완료, L4 R1의 유일한 count 결함을 수리하고 비작성자 L4 R2 대기. 작성 소유: 이 문서, `models/robot-arm-urdf-v3/`, `src/simulation/gripper_urdf/`, `outputs/urdf-gripper-v3/`만. root가 Isaac 실행/영상 069를 맡는다. 같은 작업 트리에 다른 작성자가 있으므로 남의 변경을 되돌리지 않는다.

사용자 권한: 최신 URDF에 KG1 벌림을 넣고 최신 모델로 Isaac 장면/영상 검증. 새 CAD/BOM/core/기존 URDF/이전 시뮬레이션 수정, 설치/SSH/하드웨어/플래시/재부팅/학습/구매는 이 단위 범위 밖이다. 11:53–12:38 UTC 전체 45분, L2/L4 각 최대2회; 외부 hook 추가 재시도 없음, root가 비작성자 같은 계열 검토와 외부계열 미실행 잔여를 관리한다. 기존 EXH 이력·링 보류 유지.

## 원본 실측과 좌표

- `src/cad/kmjh-gripper-v1/parameters.json`: G 원점은 붙이는 면, +X 턱 이동/+Y 깊이/+Z 접근. 부품 STL은 닫힘 u=0, A는 -X/B는 +X, `layout.stroke_half=47`mm. `gear.module=1.5`, `teeth=18`이므로 피치반경 r=13.5mm. `layout.z_c=26`mm.
- `verify_gripper.py::place/assemble/sign_check`: A는 [-u,0,0], B는 [+u,0,0], R은 G(0,0,26)mm에서 +Y축 -u/r rad. `references`의 F/A/B/R 분류는 인쇄 부품 외 혼/스플라인/나사/관의 움직임까지 명시한다. 이 분류를 그대로 재사용한다.
- `src/cad/arm-v3-kg1-assembly/parameters.json`: FLAT, render_u=20mm, 닫힘0/끝47. `models/arm-v3-kg1-assembly/assembly.json`의 G→Link6 local(28mm, 순환축)을 유지한다. 기존 v2의 J1..J6 원점/축/한계/표시 자세는 XML 구조·값 그대로 보존한다.

## 확정하려는 관절 표와 명령 계약

하나의 논리 명령 `opening_m`는 손끝 접촉면 전체 간격으로 0..0.094m. 기존 표시 자세 u20/gap40mm를 URDF q=0에 유지한다. `d=opening_m/2-0.020`m. child frame은 원점이 달라도 축은 G와 나란하다(피니언만 영점 회전).

| 이름 | parent→child | 종류/axis | zero origin xyz/rpy | 값/관계 | 한계 |
|---|---|---|---|---|---|
| KG1_slide_A | KG1→KG1_A | prismatic (-1,0,0) | (-.020,0,0)/(0,0,0) | d 독립 | [-.020,.027]m |
| KG1_slide_B | KG1→KG1_B | prismatic (+1,0,0) | (+.020,0,0)/(0,0,0) | mimic A×1+0 | [-.020,.027]m |
| KG1_pinion | KG1→KG1_R | revolute (0,1,0) | (0,0,.026)/(0,-20/13.5,0) | mimic A×(-1/.0135)+0 | [-.027/.0135,.020/.0135]rad |

A/B STL은 닫힌 원형을 G와 나란한 축 그대로 m로 변환한다. R STL은 닫힌 원형에서 축 중심(0,0,26)mm를 빼고 m로 변환한다. 피니언 zero RPY가 u20을 나타내며 mimic offset=0이고 추가 mesh 회전은 없다. 고정 KG1에는 F군만, tool0은 KG1+Z.103m의 중앙 참조점이다. 물리 movable 9축(팔6+슬라이더2+피니언1), 독립좌표7(팔6+gripper1). Isaac importer의 mimic 보존은069 실측 사항이며, 무시한다면 같은 식으로3 물리DOF에 명령하고 동적 기어 구속이라고 표현하지 않는다. MP10 목은 사용자 「한 몸 그대로」 결정 완료지만 MP9 전체 조립에는 통합되지 않았으므로 이번에도 단독 부품으로 제외한다. 기존 v2의 오래된 결정 대기 문구는 v3에 옮기지 않는다.

## 質量と衝突

기존184.2g을 분할하고 총량을 유지한다. mass-properties.json의 인쇄 부품 값을 각 군에 그대로 배분한다. 55g 서보 중 스플라인0.2g을 R에 가정 배분(나머지54.8g F), 혼3g R, 관13.19g F. 나사·인서트9g은 references의 나사 primitive 개수 F16/A4/B4/R9 합33에 비례해 가정 배분한다. 이 분할은 실측이 아니다. KG1 전체mass를 F에 중복 탑재하지 않는다. 각 군의 실제 저장 STL AABB중심/균일box 관성을 계산하고 collision도 군별 AABB 가정 proxy로 한다. 실접촉 수용은 별도다. 팔4.15kg/전체4.3342kg 유지, 물성 가정/링 보류.

## 実装と機械的受容基準

1. `assets.py`는 원CAD를 읽기만 하여 F/A/B/R 메시·질량/box계산·해시ledger를 만든다. 이전v2 팔메시는 바이트 동일 복사한다. XML 생성 pipeline은 만들지 않고 직접 작성하고 첫머리에 frame/zero/mimic/물성 가정ledger를 넣는다.
2. `verify.py`가 manifest뿐 아니라 원CAD, 실제 저장STL 정점/면, XML joint/frame/mimic/limits/질량/COM/tensor/collision을 재계산해 비교한다. 닫힘u0·표시u20·최대u47을 포함한 여러 자세에서 원CAD `gripper_items`와 독립XML FK/실mesh 정점을 비교한다. 47부품의 유일한 소속과 이전v2 표시mesh 동치, 팔 origin/axis/limits를 확인한다.
3. opening함수는 finite/non-bool 범위값만 받고 종속joint 값은 식에서 계산한다. 기존arm interface를 개명하지 않으며 root에 표를 조기 공유한다.
4. `controls.py`로 최소10개 재봉인 음성: A/B방향, zero, mimic배율/offset, pinion부호/중심/zero, limit, 중복mass, mesh변위, collision/COM/tensor, 이전팔 변경. manifest를 다시 봉인해도 공통verify가 거절해야 한다. 입력 누락도 실패한다.
5. 등록된cadgen0.8.2 direct console로 strict validate 0issue. CAD Viewer에 실제 모델을 표시하고 leader 닫힘/표시/최대snapshot에서 새 종속관절도 같이 움직임을 확인한다. 기존팔6축도 각 한계snapshot으로 확인한다(물리 안전범위가 아니다). 외부check_urdf 부재는SKIPPED.
6. 작성자host 검사 후 root가 비작성자 L4 최대2를 수행한다. SDK runtime은069가 별도 실측하며 068 정적PASS를 Isaac성공이나 실기수용으로 승격하지 않는다.

## 状態原簿

L2 R1: PASS9/0(root 수신, 검토본SHA256 9A43E94BB7C56BA9F6240EED12F2D3EB152B830F442782004776287572A11E9D) / L3: 구현 완료 / L4 R1: BLOCK8/1(GR068-R1-1) / L4 R2: PENDING. 새 단위EXHAUSTED 판정은 비작성자만 한다. SDK·접촉·학습·실기는 이 단위에서 NOT_RUN.

작성자 결과: strict cadgen0.8.2 `ok=true/issues=[]`, 물리11mesh/12link/9movable. 독립 arm FK 및 실제 CAD 동작20자세(u0/10/20/35/47, 팔6관절 양한계와 복합자세): mesh변환 최대3.70e-9m, CAD 실정점 동작 최대4.14e-9m, 기존 u20 표시mesh 전체triangle 동치 최대3.91e-9m, 독립FK 최대1.52e-15. 단정밀도 STL 변환 오차이며 실물 정밀도가 아니다. 그리퍼.1842kg/전체4.3342kg, 원본94입력 해시 불변. `verification.json`이 수치 원본이다.

재봉인 음성20/20 의도한 검사 거절 및 원본 전후PASS/해시불변(`semantic-controls.json`). `cad_show`의 열린 viewer 없음 응답 뒤 `cad_open` 한 번으로 실제 모델 탭을 표시했다. 공식MCP snapshot18장(표시/닫힘/최대 +팔6관절 양한계 +그리퍼 정면3자세)은 모두11parts/unmeshed없음/warning없음으로 성공했다. `snapshot-sweep.json`이 pose와 완료 결과를 보존한다. 전체 팔12한계 contact-sheet와 닫힘/표시/최대 이미지를 작성자가 직접 봐서 축별 움직임과 분리된 턱이 정상임을 확인했다. CLI snapshot 한 번은 sandbox LOCALAPPDATA의 engine 불일치로 실패했고 공식 MCP snapshot으로 정상 실행했다. `cad_inspect`의 URDF 구조조회는 지원되지 않아 실패했으며 검증 근거로 사용하지 않았다. 외부 check_urdf는 현재 PATH에서 찾지 못해 SKIPPED다.

L4 R1 GR068-R1-1 수용: 원래 controls는 `expected_controls=len(cases())`라서 빈 목록도 all_caught=true가 됐다. 원본script/report를 `outputs/urdf-gripper-v3/review/r1-original/`에 보존했다. 수리 전 원본을 별도 모듈로 불러 cases만 빈 목록으로 바꾼 HOSTshim이 expected0/all_caughttrue를 실제 재현했다. 수리판은 고정EXPECTED_CONTROLS=20/고정20이름과 실제 목록·결과의 count/일의성/완료·양성baseline·reseal을 검사한다. 0/19/중복/역순 목록4개와 0/19/중복 report3개를 거절했고 정상20report를 수용했다. 독립 재현 경로는 `src/simulation/gripper_urdf/count_regression.py`, 원자료는 `review/r1-count-repair.json`. 원본 XML SHA256 9cbbebe2ecfebd08436aa77c2760c281319eeca82c195108f177a15f2d6b2d2c와 모든 모델 바이트는 수리 중 불변이다. 최종20case는 새 고유 폴더에서 다시 실행하고 옛 결과를 보존한다. R2 최종판정/EXH 처분은 root의 비작성자 기록을 따른다.
