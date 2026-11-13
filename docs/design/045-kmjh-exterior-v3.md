> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 045 — MP7 외장 v3: KMJH 브랜드로 다시 그린 1:1 외장 + 블렌더 장면 (Claude 모델링)

> **상태: 비작성자 최종 검수 미통과 — 마지막 지적 1건은 고쳤으나 재검수 없음**(2026-10-27 · 사용자 결정 「‘검수 미통과’ 표지로 커밋 (권장)」).
> L2 R1 · R2(NEEDS_ATTENTION · 예산 소진) → L4 R1 · R2 · R3(NEEDS_ATTENTION · Major 4 → 2 → 1 · 예산 소진). 지적은 모두 검사 장치였고 산출 결함은 L4 세 번
> 모두 없음. 처분 = `.dev/product-v3-evidence/mp7-*-disposition.md`.

사용자 요청(2026-10-27, 원문): 「자 이제 그럼 전에줫던 상표를 기준으로 모델링을 좀더 예쁘게 만들어봐 그리고 끝나면블랜더까지 참고로 지금 URDF준비중이니 관절거리는 일단 건들지말고」.
「상표」 = 2026-10-26 사용자가 보낸 KMJH 브랜드 그림 두 장(`docs/brand/README.md` · `docs/brand/kmjh-0*.webp`).

계획 번호 045 는 MP7 이 쓴다(Codex 가 039 까지 쓰는 중이라 040 ~ 044 를 비워 둠).

## 범위 · 불변

- **새 폴더만 만든다**: 생성기 `src/cad/armold-mks-product-v3/` · 산출 `models/armold-mks-product-v3/` · 블렌더 `models/armold-mks-product-v3/blender/` · 기록
  `.dev/product-v3-evidence/`.
- **관절 거리 불변**(사용자 지시): 관절 원점 · 세계 축 · 링크 회전 · 길이 = `models/armold-mks-concept-v1/kinematics.json` · `parameters.json` 그대로 읽기만.
  표시 자세 `[15, -50, 70, 15, 25, -10]` 도 v2 와 같다. 드럼 지름 · 깊이 36 · 모터 캔 반지름 39 · 캔 길이 · 출력 방향도 v2 값 그대로(모터 · 드라이버 가정 상자가
  들어가는 자리).
- **v2 를 고치지 않는다**: `models/armold-mks-product-v2/` · `src/cad/armold-mks-product-v2/` 는 Codex 의 관절 정렬 · 방향 · 기동 검사(계획 022 · 024 ·
  025 등)가 해시로 묶어 두었다(CODING_RULES MP5: 「레이아웃을 바꿔야 하면 v2 가 아닌 v3 로 한다」). v3 생성기는 v2 코드를 가져오지 않는다.
- 하지 않는 것: v1 · v2 · J2 분할 · MP6 · 펌웨어 · Codex 계획(001 ~ 039) 수정, URDF 작성(사용자가 준비 중), 출력 · 프린터 전송 · 구매, 벽 두께 · 속 공간 ·
  체결(v2 와 같은 외곽 덩어리 — 제작 도면 아님).

## 디자인 (브랜드 → 형상 · 색)

브랜드 문서의 「모델링에 옮기는 법(작성자 제안)」 을 따른다. 색은 그림 표기값 그대로 넷만 쓴다.

| 역할 | 색 | 쓰는 곳 |
|---|---|---|
| body | White `#FFFFFF` | 관절 모듈(드럼 + 모터 캔) · 허브 · 링크 막대 · 어깨 기둥 · 목 · 베이스 기둥 |
| accent | Deep Navy `#0B2545` | 출력 쪽 띠(v2 주황 자리) · 관절 끝 덮개(v2 주황 자리) · 허브 바깥 원판 덮개 · KMJH 글자 |
| frame | Cool Gray `#6B7280` | 베이스 발(v2 진회색) · 공구 플랜지 |
| highlight | Mint Accent `#34D399` | 끝 덮개 · 허브 덮개의 45° 사선 · K 의 사선 · 베이스 빛 띠 · 공구 끝 고리 |

형상(관절 거리와 무관한 겉모양만):
1. 둥근 필렛 → **45° 모따기**: 드럼 뒤 모서리 4 · 허브 4 · 끝 덮개 2 · 어깨 덮개 6 · 베이스 발 4 · 공구 플랜지 2 (회전 단면에 바로 넣음).
2. 둥근 관 → **모따기한 팔각 막대**(같은 중심선 · 같은 반폭): 상완 · 전완 반폭 22 · 모따기 8, 손목 17 · 6. 어깨 기둥 · 손목 목도 둥근 사각 → 팔각.
3. 전완 · 손목 막대가 다음 관절 모터 캔 옆에서 끝나며 캔 밖으로 튀어나오던 끝(v2 에도 있음)을 **45° 로 잘라** 캔 안(반지름 39 − 0.5)에서 만나게.
4. 표시: 끝 덮개 다섯(J2 ~ J6)과 허브 바깥 면 셋(어깨 · 팔꿈치 · 손목)에 남색 원판 + 민트 45° 사선(0.8 돋움). 상완의 앞에서 보이는 면(−y)에
   **KMJH 글자**(글자 높이 13 · 0.8 돋움 · K 의 위 사선만 민트). 글자는 작성자가 사용자 그림을 보고 그린 다각형(`kmjh_logo.py`)이며 원본 로고 파일이 아니다 —
   J2 드럼(반지름 52) 위에 얹히지 않게 x > 52 에만 둔다.

치수는 `src/cad/armold-mks-product-v3/parameters.json`. 겉모양은 사용자의 눈으로 판정한다(그림 · 블렌더 렌더) — 사용자가 고치라는 곳은 관절 거리와
무관한 값만 바꿔 다시 만든다.

## 블렌더 (「끝나면블랜더까지」)

Blender 5.2.3(`C:\tools\Blender-5.2.3\…\blender.exe` · 설치되어 있음 — 새 설치 없음)를 화면 없이(`--background`) 돌리는 스크립트
`src/cad/armold-mks-product-v3/blender_scene.py`:
- SolidCraft 가 바디마다 쓴 STL(세계 좌표 mm · 표시 자세)을 가져와 m 로 줄이고, `bodies.json` 의 역할대로 재질 넷(Principled — 색 = 브랜드 값 · 무광 플라스틱 ·
  민트는 같은 플라스틱)을 붙인다.
- **관절 빈 객체 6 개**를 v1 원점 · 축(로컬 Z = 관절 축)에 두고 링크 k 의 객체를 관절 k 빈 객체의 자식으로, 빈 객체끼리는 부모 → 자식으로 잇는다 —
  블렌더에서 빈 객체의 Z 회전만 돌리면 그 관절 아래가 따라 돈다(X · Y 회전 잠금). URDF 를 대신하지 않는다(보기 · 렌더용).
- 스튜디오 조명 · 바닥 · 카메라 셋(정면 3/4 · 정면 · 상완 글자 가까이) → Cycles 렌더 PNG 셋 · `.blend` · 색 있는 GLB 하나.

## 쓰기 가드 · 보호 스냅숏 (L2 R1 F3 · F4 · R2-02 · 03 · 04)

- `guard.py`: 저장소 루트를 못 찾으면 멈춤(절대 경로로 돌아가지 않음). 기존 파일이 하드 링크(링크 수 > 1)면 쓰지 않음(L4 R1 F2). 폴더 트리 지우기는 `safe_rmtree` — 트리 안 모든 폴더 · 파일을 먼저 가드하고
  하나라도 걸리면 아무것도 지우지 않음(L4 R2-F2). 쓰기 폴더는 만들기 전에 `checked_dir`, 쓰거나 지우거나 SolidCraft · Blender 에 넘기는
  **파일 하나하나**는 그 직전에 `checked_file` — 끝까지 푼 경로가 v3 산출 · v3 근거 · 격리 작업 뿌리 아래만 · 보호 폴더(v1 개념 · v2 산출 · v2 생성기 —
  `guard.PROTECTED_REL` 상수) 안이나 그 위 거부 · 경로의 어느 조각이든 링크 / 정션이면 거부(자식 `meshes` 정션 포함).
- **격리 작업 뿌리**(`--scratch-root`)는 미리 만든 폴더만: 표지 파일 `MP7_SCRATCH` · 자기나 조상에 `.git` 없음(실 저장소 · `C:\projects` 거부) · 보호 폴더
  경로를 품지 않음 · 저장소와 겹치지 않음. 양성 대조 산출(`--control`)은 그 아래로만.
- `snapshot.py`: 보호 폴더 셋의 **모든 파일**(추적 · 미추적 · 무시)을 바이트 해시로 — 덮어쓰지 않고 UTC 시각 · 명령 · HEAD · sha256 옆 파일을 남김.
  시작 기준선 `.dev/product-v3-evidence/protected-snapshot-before.json`(sha256 `35ca6f30…` · 54 파일 · HEAD `b5f4153`)은 첫 판 도구로 떴다 —
  만든 시각 23:27:17Z 가 첫 저장소 산출 23:39:45Z 보다 앞(파일 시각 · 약한 근거 — `protected-snapshot-before.provenance.json`).

## 검사 (자동 — `validate_product.py` · `expected_shapes.py` · `blender_scene.py` · `blender_verify.py`)

- **독립 정답표**(`expected_shapes.py` · R2-01): 검사기가 생성기 코드를 쓰지 않고 47 바디의 이름 · 링크 · 역할 · 기대 형상(세계 mm · 표시 자세)을 다시 만든다 —
  프레임 = C1a 순기구학 · 보호 치수 = v1 / v2 parameters · 겉모양 값(모따기 · 표시 · 글자) = v3 parameters · kmjh_logo. 회전체 720 등분 · 각기둥 정확 ·
  45° 끝 자르기 = manifold 불리언.
- **C0 출처 묶음**(L4 R1 F1): 생성기가 남긴 `build/provenance.json`(native · STL 47 · 기록의 sha256) = 지금 파일 · 간섭과 평가(`eval-now.json`)는 검사기가
  정상 실행 때 **지금 native 로 새로** 내고 `check-provenance.json` 에 native · 결과 sha256 을 묶는다(parse-only 는 저장 결과가 지금 native 의 것일 때만 참).
- C1 관절 = v1: native 관절 여섯 revolute 의 원점 차 ≤ 1e-6 mm · 단위 축 성분 차 ≤ 1e-9 — SolidCraft `joint.list` **와 native 문서의 관절 양쪽 snap 을 직접**.
- C1a v1 parameters 의 길이 · 축과 pose_deg 로 다시 계산한 순기구학 = kinematics.json(1e-9).
- C1b 회전체 무게중심이 그 관절 축 위(≤ 1e-3 mm).
- C1c native 구조(컴포넌트 7 · 발생 7 단위 변환 · Base 만 고정 · 관절 사슬 · 값 0) · **native 소속 · bodies.json 링크 / 역할 · 바디 이름 집합 = 독립 정답표**.
  C2 · C3 의 링크 소속은 정답표로 판정.
- C1d 링크 좌표 범위(모듈 축 범위 · 드럼 · 캔 반지름 · 출력 쪽 · 덮개 · 띠 · 허브 · 막대 x 0 … 165 · 목 · 기둥 · 베이스 · 공구 98 항목) = v1 · v2 값 0.01 mm ·
  v3 parameters 보호 키 = v2.
- **C1e** 바디마다(47) 독립 기대 형상 ↔ STL **양방향 표면 거리 ≤ 0.03 mm**(STL 꼭짓점 → 기대 표면 · 기대 표면의 꼭짓점과 표본 4000 → STL 표면) —
  국소 모따기 · 끝 자르기 · 글자 · 덮개까지.
- C2 표시 자세 정확 커널 간섭: 응답이 완전(interferences · `unchecked == []` · `pairs_not_checked == 0` · 예산 초과 · 잘림 없음 — L4 R1 F4) · 서로 다른 링크 0. C2b 표시(사선 · 허브 덮개 · 글자)는 어떤 바디와도 체적이 겹치지 않음.
  **표시 자세 한 자세만** — 다른 자세 · 연속 회전의 충돌 · 여유는 검사 밖.
- C3 v1 가정 상자 18 개가 그 관절 모듈 안 100 % · 다른 링크와 간섭 0.
- C4 보호 폴더(상수 셋)의 모든 파일 = 시작 기준선(기준선의 roots 가 상수와 같고 셋 모두 파일 있음) · v1 동결 목록 · (git 있을 때) v2 추적 = HEAD.
  대조 모드(`--protected-root` = 작업 뿌리 아래 사본)는 키 `C4_CONTROL_copy_equal_start_snapshot` · `mode: control` · `acceptance: false` 로 정상과 갈림.
- C5 native 에 **저장된** 바디 색 = 이름 역할 = 정답표 역할의 브랜드 RGB · 팔레트 = 브랜드 넷 · 바디 집합 일치.
- C6 STL 하나씩(남는 파일 없음) · 닫힘 · native 평가와 상자 · 무게중심 **0.002 mm**(native 기준 오차 예산 = C1d 0.01 + 0.002) · 체적 · 넓이 0.2 %.
- C6b 특징 체적(native) = 독립 계산: 평면 바디(글자 · 사선 · 막대 · 목 · 기둥) 1e-6 · 원기둥 면이 있는 허브 덮개 셋 2e-4(native 평가 체적이 곡면 분할 값이라
  약 6e-5 작게 나옴 — 형상은 C1e 가 0.03 mm 로 본다).
- C7 블렌더(`blender_scene.py`): 가져온 직후 · 부모 뒤 바디마다 **STL 점(블렌더 밖에서 직접 읽음 · mm × 0.001)과 점 하나하나** 양방향 최근접 ≤ 2e-7 m ·
  **삼각면(감김 포함) 다중집합 = STL · 입력 면 수 = STL 삼각면 수 · 번호 사상 뒤 퇴화해 버린 면 0**(L4 R1 F3 · R2-F3) · 객체 회전 / 축척 = 단위 · 부모 사슬 · 잠금 · 장면 m · 객체 종류 수 · 메시 이름 = 바디 47 + 바닥 · 재질 슬롯 하나 · 모든 면 색인 0 · Base Color 값 = 브랜드 색 · 빈 객체 위치 · 축 = v1(1e-6) ·
  모든 꼭짓점 ±10° · 조합 자세 · 되돌림 · 기하 영점 = v1 q = 0 순기구학 · 렌더 넷이 요청 크기 + **카메라 광선 64 × 48 의 가시성**(전체 그림: 로봇 화면
  5 % 이상 · 바디 20 이상 · 흰 몸체 8 이상 / 글자 그림: 글자 다섯 모두 · 렌더 숨김 제외) + 남색 · 민트 화소.
- C7v(`blender_verify.py` · 새 프로세스): 다시 연 .blend 의 바디마다 STL 점 · 삼각면(감김) 대조 · 재질 슬롯 · 면 색인 · 색 · 부모 사슬 · 잠금 · 빈 객체 · J2 회전 ·
  단위 · 종류 수 · 메시 이름 목록, GLB 를 빈 장면에 가져와 바디마다 STL 점(2e-6 m) · 삼각면(감김) · 브랜드 색 · 메시 이름 목록(바디 47 + 바닥).

## 양성 대조 (작성자 — `run_controls.py` → `controls.json`: 대조마다 목표 검사 키가 거짓 · 정상 모델은 모든 검사 PASS)

| 대조 | 일부러 넣는 잘못 | 목표 검사 |
|---|---|---|
| `logo_on_drum` | 생성기의 x > 52 확인을 끄고 글자를 x = 30(J2 드럼 위)에 실제로 만든다 | C2 서로 다른 링크 간섭 |
| `bar_shift` | 상완 막대만 x 로 1 mm — 관절 그대로 | C1d |
| `joint_origin` | J3 관절 객체만 x 로 1 mm — 형상 그대로 | C1 |
| `can_short` | 모터 캔 12 mm 짧게 | C3 |
| `cap_color` | J2 끝 덮개를 흰색으로 칠함 — bodies.json 은 남색 그대로 | C5(저장 색) |
| `owner_both` | 공구 플랜지를 Link5 컴포넌트 · bodies.json 링크 5 로 **함께** | C1c(독립 정답표) |
| `drop_ring` | 공구 끝 고리를 어디에도 만들지 않음 | C1c · C1e |
| 보호 폴더 사본(대조 모드) | 사본에서 v2 파일 한 바이트 · 새 파일 · 삭제 | `C4_CONTROL_…` |
| `protected_baseline_narrow` | 기준선을 v1 한 폴더로 좁힘(정상 모드) | C4 |
| `mesh_box` · `mesh_open` | 글자 STL 을 상자로 · 막대 STL 면 하나 지움 | C6 |
| `mesh_local_chamfer` | 상완 막대 모따기 가운데 2 mm 에 1.5 mm 홈(닫힌 메시) | C1e |
| `eval_shift` | native 평가 기록의 막대 상자 · 무게중심 0.04 mm(STL 그대로) | C6 |
| `native_doc_joint` · `native_logo_extrude` | 사본 native 문서의 J3 관절 snap +1 mm · 글자 K 밀기 0.8 → 1.6(저장 기록 그대로) | C1 문서 · C0 |
| `check_no_unchecked_key` · `check_pairs_not_checked` · `check_truncated` | 사본 간섭 기록에서 unchecked 키 삭제 · 미검사 1 · 잘림 / 예산 초과 | C2 완전성 |
| 쓰기 가드 | **가드 함수만**: 하드 링크 로그 · 파일 심볼릭 링크(권한 없으면 NOT_RUN) · 하드 링크 / 정션이 든 트리 지우기 거부(무삭제 확인) · 보통 트리 지우기 · 보호 폴더 · 그 위 · 대소문자 · `..` · 정션 · 허용 폴더 아래 자식 정션 · 저장소 안 작업 뿌리 · 실 저장소 / `C:\projects` / 표지 없는 폴더를 작업 뿌리로 · 사본 기준에서 실 저장소를 작업 뿌리로 · 스냅숏 출력을 v2 로 (+ 허용 경로) | 거부 / 허용 |
| 블렌더 `no_scale` · `flip_axis` · `wrong_parent` · `mixed_material` · `hide_robot` · `nudge_vertex` · `hide_body_white` · `camera_away` · `flip_winding` | mm 그대로 · J3 축 반대 · 링크 3 을 J2 에 · J2 모듈에 민트 · 로봇 숨김 · 꼭짓점 하나 1 mm · 흰 몸체만 숨김 · 카메라 반대쪽 · 막대 면 감김 뒤집기 | C7 해당 줄 |
| 저장물 `blend_move_body` · `glb_move_body` · `blend_face_material` · `blend_flip_winding` · `glb_shuffle_faces` · `glb_extra_mesh` · `blend_degenerate_face` · `glb_sliver_face` | 다시 연 .blend 의 바디 1 mm · GLB 바디 1 mm · 면 하나 재질 색인 1 · .blend 감김 뒤집기 · GLB 면 연결 섞기 · GLB 메시 더하기 · 퇴화 면 더하기 · 1e-7 m 새 점으로 가는 유한 면 더하기 | C7v 해당 줄 |

## 검수

- L2(이 계획) 최대 2 회 · L4(구현 · 산출 · 렌더) 최대 3 회 — Codex `gpt-6.1-sol` · high · 사본에서 읽기 전용.
- 겉모양(예쁜가)은 검수 대상이 아니다 — 사용자가 렌더로 판정. 검수는 위 불변 · 검사의 빈틈을 본다.

## 남는 것 · 한계

- 외곽 덩어리(v2 와 같음): 벽 · 속 · 체결 · 케이블 통로 · 부품 분할은 아직(계획 014 의 B).
- KMJH 글자는 작성자의 그림 — 원본 로고 벡터를 받으면 `kmjh_logo.py` 만 바꿔 다시 만든다.
- 블렌더 관절 빈 객체는 보기용 — 관절 범위 · 질량 · 충돌 모델 없음(URDF 는 사용자 작업).
