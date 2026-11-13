# KMJH v3 rev1 + KG1 — URDF v2

정본은 직접 작성한 `robot_arm.urdf`다. 계산 보조는 `src/simulation/urdf_revised/`이며 XML 생성기가 아니다. 전체 조립은 MP9 rev1의 v3 외장 + KG1이고 팔 STL 47바디와 그리퍼 47구성체(인쇄6·구매품 기준입체41)를 링크별8STL로 합쳤다. MP10 J5 실부품은 목 결정 대기인 별도 모듈이므로 이 조립에 적용하지 않았다. MP11 분해도도 치수 원천으로 쓰지 않았다.

9링크 = 물리8(Base·Link1..6·KG1) + frame-only tool0, 6 revolute + 2 fixed. 관절 원점·축·거리와 이름은 기존 v1과 동일하다. q=0은 표시 자세 [15,-50,70,15,25,-10]°이며 실제 로봇 영점이 아니다. q 단위는 표시 자세로부터 delta rad이다. 메시 좌표는 링크 지역 **m**, mesh scale은1이다. 외장 mm 세계좌표를 각 링크 표시 프레임으로 역변환하고 0.001배했다.

KG1 G 프레임은 MP9 `g_to_link6_local`을 그대로 사용한다. Link6 +X28mm에 장착하며 G x/y/z = Link6 y/z/x이다. FLAT 손끝, 한 턱 벌림 u20mm(틈40mm)에서 **고정 공구**다. 개폐 조인트·서보 제어·감속기 내부 DOF는 없다. tool0는 G +Z103mm, J6 축에서131mm인 명목 쥐는 점이며 실측 TCP가 아니다.

## 물성과 범위

총4.3342kg은 arm의 기존 임의 질량4.15kg + KG1 추정 질량0.1842kg이다. 모든 COM은 실제 저장한 링크 STL의 AABB 중심, 관성은 그 질량의 균일상자 공식으로 계산했다. KG1 원본 COM은 닫힌 자세 값이므로 u20에 전용하지 않았다. collision도 각각의 AABB이며 과대 접촉이 생길 수 있다. `asset-ledger.json`은 실제 메시로부터 계산한 숫자와 원본 소유권 목록이다. 실측 물성·CAD 질량·충돌 수용 자료가 아니다.

J1/J2/J3/J4/J6 ±170° delta는 예시다. J5는 MP9의 표본 스크리닝 절대각[-110,110]°를 표시25°에 대해 delta[-135,85]°로 바꿨다. 실제 기계 한계나 그 범위 안 모든 경로의 간섭 없음은 확인하지 않았다. effort[3,6,5,2,2,1]Nm·velocity0.5rad/s·damping0.05·friction0도 가정이다. CAN ID/실물 영점/모터·encoder 부호/실측 감속비는 UNKNOWN이다.

## 검증과 재현

저장소 루트에서 기존 printforge Python을 읽기 전용 의존성 런타임으로 사용한다. 설치하지 않는다.

```powershell
& C:/projects/printforge/.venv/Scripts/python.exe -X utf8 -I -B src/simulation/urdf_revised/verify.py
```

작성자 정적 검사: 실제 XML 재파싱28자세/168관절 프레임 독립 FK와 실제 저장 STL 대조 PASS. reseal한 모순 자산13개가 의도한 의미 검사에서 모두 거절됐고 정상 자료 전후 PASS. cadgen0.8.2 실제 strict validator는 오류·경고0이다. 원자료는 `outputs/urdf-revised-v2/`에 있다. 비작성자 L4 판정과 시각 검토 상태는 그 폴더의 HANDOFF를 따른다.

새 모델의 Isaac/USD import·동역학·접촉·중력·경로추종·RL·실물은 **NOT_RUN**이다. 065의 기존 동역학 통과를 상속하지 않는다. 링 형상 검증 보류와 기존 provenance7/physical6 EXHAUSTED·eligibility2-next1·first-fault/047/063/064 실패 이력을 유지한다. 이번 정적 모델은 운전 승인이나 물리 안전범위를 제공하지 않는다.

`provenance.json`은 읽은 입력81개의 path/bytes/SHA, `manifest.json`은 실제 패키지 파일 SHA다. 기존 CAD/BOM/core/펌웨어/구 URDF와 시뮬레이션 코드는 변경하지 않았다. 메시 합치기로 원래 바디별 색은 링크별 색으로 단순화했다. 형상·소유권은 보존했다.
