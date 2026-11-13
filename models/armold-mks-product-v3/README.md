# KMJH 6축 — 1:1 제품 외장 v3 (MP7 · 2026-10-27) — 사용자 브랜드 KMJH 로 다시 그림

> **비작성자 최종 검수 미통과 — 마지막 지적 1건은 고쳤으나 재검수 없음**(2026-10-27 · 사용자 결정 「‘검수 미통과’ 표지로 커밋 (권장)」).
> L2 2 회 · L4 3 회 모두 NEEDS_ATTENTION 이었고 지적은 전부 **검사 장치**(검사기 · 쓰기 가드 · 블렌더 대조)의 빈틈이었다. 검수자는 L4 세 번 모두 산출을 직접
> 계산해 **관절 거리 · 보호 파일 · 브랜드 색 전달 · 블렌더 / GLB 에 결함 없음**을 확인했다. 마지막 지적(지울 폴더 자리에 하드 링크 파일)은 고치고 가드 대조로만
> 확인했다. 기록 = `.dev/product-v3-evidence/`(검수 원문 · 처분 · `user-decisions-mp7.json`).

> **rev1(2026-10-28 · MP9 2 단계 · 계획 `docs/design/051-arm-v3-gripper-assembly.md`)** — 사용자 「v3 민트 고리를 그리퍼 규격(Ø20 × 1.5 돌기 + M3 Ø31.5 나사 자리)에 맞게
> 고쳐서 다시 붙여줘」: 공구 끝 **민트 고리(Ø40 × 4) → 돌기 Ø20 × 1.5**(바디 이름 `LINK6_TOOL_RING` · 민트 그대로) · **공구 플랜지에 M3 열압입 인서트 구멍 넷 Ø4.0 × 깊이 8 · Ø31.5 원 · 0° / 90° / 180° / 270°**
> (링크 6 지역 y 에서 z 쪽). 숫자의 원천 = 그리퍼 `src/cad/kmjh-gripper-v1/parameters.json`(맞춤 홈 · 팔 나사) · 끼움 원장 `insert_hole_dia`(확정) — 여기 parameters 에는 경로만.
> 돌기는 공칭(틈 0 · 보기 · 맞춤 확인용 — 실제 출력 부품이면 원장의 끼움 틈이 필요). 다른 바디 45 개의 메시는 바이트 그대로 · 관절 거리 · 축 그대로. 검사 20 개 다시 참(`validation.json`).
> **rev1 은 Codex 비작성자 검수를 받지 않았다**(Claude 하위 에이전트 산출 검토만 — `.dev/mp9-evidence/review-b.md`) · 위 MP7 검수 문장은 rev0 에 대한 것.
> 🔴 **아래의 갤러리(`blender/gallery/` · `gallery-report.json`) · 동작 영상(`blender/motion/` · `.dev/product-v3-evidence/motion-controls.json` · 장면 고정 `src/cad/armold-mks-product-v3/motion_scene_pin.json` = 옛 .blend `2db0af54…`)과
> 그 검사 기록은 rev1 이전(옛 고리)으로 찍혔고 다시 렌더하지 않았다** — 그 검사들은 바뀐 `.blend` 로 이제 거짓이 된다(다시 렌더는 사용자 결정). 장면 렌더 넷 · `.blend` · GLB 는 rev1 로 다시 만들었다. 그리퍼를 붙인 조립 = `models/arm-v3-kg1-assembly/`.

사용자 요청: 「자 이제 그럼 전에줫던 상표를 기준으로 모델링을 좀더 예쁘게 만들어봐 그리고 끝나면블랜더까지 참고로 지금 URDF준비중이니 관절거리는 일단 건들지말고」.
계획 = `docs/design/045-kmjh-exterior-v3.md` · 브랜드 = `docs/brand/README.md` · 생성기 = `src/cad/armold-mks-product-v3/` · 기록 = `.dev/product-v3-evidence/`.

**관절 거리 · 축은 그대로**: 관절 원점 · 세계 축 · 링크 길이(어깨 96 + 78 · 상완 165 · 전완 140 · 손목 78 / 140 mm) · 표시 자세 `[15, -50, 70, 15, 25, -10]` 도 ·
드럼 지름 · 깊이 36 · 모터 캔 반지름 39 · 캔 길이 · 출력 방향은 v1 / v2 와 같다(검사 C1 · C1a · C1d 가 메시로 확인). v2(`models/armold-mks-product-v2`)는
그대로 있다 — 다른 작업(관절 정렬 검사)이 해시로 묶어 두어 v3 를 새 폴더로 만들었다. **외곽 덩어리이며 제작 도면이 아니다**(벽 · 속 · 체결 없음 — v2 와 같음).

## 바뀐 것 (겉모양만)

| | v2 | v3 |
|---|---|---|
| 색 | 흰 · 주황 · 진회색 | **흰 `#FFFFFF` · Deep Navy `#0B2545` · Cool Gray `#6B7280` + Mint `#34D399` 강조**(브랜드 그림 표기값) |
| 관절 띠 · 끝 덮개 | 주황 | 남색 · 끝 덮개마다 민트 45° 사선(0.8 돋움) |
| 모서리 | 둥근 필렛 | 45° 모따기(드럼 4 · 허브 4 · 덮개 2 · 어깨 덮개 6 · 베이스 발 4 · 공구 2) |
| 링크 | 둥근 관 | 모따기한 팔각 막대(같은 중심선 · 같은 반폭) · 어깨 기둥 · 손목 목도 팔각 |
| 전완 · 손목 끝 | 관 끝이 모터 캔 밖으로 튀어나옴 | 캔 밖 부분을 45° 로 잘라 캔 안에서 만남 |
| 허브 바깥 면(어깨 · 팔꿈치 · 손목) | 흰 원판 | 남색 원판 + 민트 사선 |
| 표시 | 없음 | 상완 앞면에 **KMJH**(글자 높이 13 · K 의 위 사선만 민트) · 베이스 빛 띠 · 공구 끝 고리 = 민트(rev1: 고리 → 그리퍼 규격 돌기 Ø20 × 1.5 · 플랜지 M3 인서트 구멍 넷) |

KMJH 글자는 작성자가 사용자 그림을 보고 다각형으로 그린 것(`src/cad/armold-mks-product-v3/kmjh_logo.py`)이다 — 원본 로고 벡터를 받으면 그 파일만 바꿔 다시 만든다.

## 파일

| 파일 | 내용 |
|---|---|
| `kmjh-arm-product-v3.solidcraft` | 편집 이력 있는 native — Base + Link1 … Link6 · revolute 6(관절 0 = 표시 자세) · 바디 47 |
| `kmjh-arm-product-v3.step` · `.3mf` | 형상(3MF 는 바디 색 포함) |
| `meshes/*.stl` | 바디마다 STL 47(세계 좌표 mm · 표시 자세) — 블렌더 장면의 입력 |
| `iso.png` · `front.png` · `right.png` | SolidCraft 그림 |
| `bodies.json` | 바디 → 링크 · 색 역할 · 색 |
| `validation.json` | 검사 C1 ~ C6 결과 |
| `blender/kmjh-arm-v3.blend` | 블렌더 장면(브랜드 재질 넷 · 관절 빈 객체 · 조명 · 카메라) |
| `blender/kmjh-arm-v3.glb` | 색 있는 GLB(m · 어디서나 보기) |
| `blender/render-hero.png` · `render-front.png` · `render-logo-detail.png` · `render-zero-pose.png` | Cycles 렌더 1600 × 1200(3/4 · 정면 · 글자 · 기하 영점 자세) |
| `blender/scene-report.json` · `verify-report.json` | 블렌더 검사 C7 · 저장물 다시 열기 검사 C7v |

## 갤러리 — 여러 각도 · 자세 · 흰 ↔ 회색 바꿈 (2026-10-27 추가 · 비작성자 검수 없음)

사용자 「예쁘네 좀더 다각도와 추가 자세로 만들어줄래 ? 그리고 흰색이랑 회색이랑 역전해서도 만들어보고」. 형상 · 관절 거리 · 커밋된 `.blend` 는 그대로이고
**그림만 더한 것**이다(블렌더 장면을 읽기만 하고 저장하지 않음 — 검사 `G_blend_not_modified`). 이 추가분은 비작성자 검수를 받지 않았다.

- `blender/gallery/brand/` · `blender/gallery/swap/` — 같은 18 샷을 두 색 조합으로(JPEG 1600 × 1200):
  표시 자세 한 바퀴 8 방향(45 도마다) · 위에서 · 낮게 · 손목 확대 · 글자 확대 + 자세 6(ㄱ 자 대기 · 위로 뻗기 · 아래 집기 · 옆으로 뻗기 · 손목 비틀기 · 기하 영점).
- **swap** = 흰 몸체 ↔ Cool Gray 를 맞바꿈(몸체 `#6B7280` · 베이스 발 · 공구 플랜지 `#FFFFFF` · 남색 · 민트 그대로). 렌더만 — native · 3MF · GLB 의 색은 브랜드 그대로다.
- `blender/gallery/sheet-brand.jpg` · `sheet-swap.jpg`(한 장에 모아 보기) · `compare-brand-swap.jpg`(같은 샷 나란히).
- 자세 = `src/cad/armold-mks-product-v3/gallery_poses.json`(q = 기하 영점 기준 · 빈 객체 Z 회전 = q − pose_deg).
- `blender/gallery/pose-check.json` — `pose_check.py` 가 블렌더 없이 커밋된 STL 을 v1 축으로 돌려 자세마다 계산: 관절각 ±170 도 안 · 서로 다른 링크 바디 쌍의
  겹친 부피(manifold3d · 모두 0.05 mm³ 이하 — 접촉면 분할 오차 수준) · 이웃 아닌 링크 꼭짓점 거리 2 mm 이상(꼭짓점 기준 근사) · 움직이는 링크가 바닥 위 5 mm 이상.
  일부러 부딪히게 한 자세 셋(팔꿈치 접기 · 팔 내리기 · 손목 접기)은 모두 잡았다(시험 기록은 작업 뿌리에만). **정지 자세만** 보며 자세 사이 움직임 · 실제 관절 범위는 보지 않는다.
- `blender/gallery/gallery-report.json` — 장면 메시 = STL · 자세마다 모든 꼭짓점 = 표시 자세 점을 v1 축으로 돌린 값 · 재질 색 = 조합 값 · 렌더마다 카메라 광선으로
  로봇 · 몸체 · 남색 · 민트 바디가 보임 · `.blend` 해시 그대로.
- 렌더 장면은 메모리에서만 둘 바꾼다: 조명이 카메라와 함께 돈다(어느 방향이든 같은 빛) · 카메라에 보이는 먼 바닥을 배경색으로 서서히(검은 지평선 띠 없앰).

```
python src/cad/armold-mks-product-v3/pose_check.py --model models/armold-mks-product-v3 --kin models/armold-mks-concept-v1/kinematics.json --poses src/cad/armold-mks-product-v3/gallery_poses.json --out models/armold-mks-product-v3/blender/gallery/pose-check.json
blender --background --factory-startup --python src/cad/armold-mks-product-v3/blender_gallery.py -- --blend models/armold-mks-product-v3/blender/kmjh-arm-v3.blend --model models/armold-mks-product-v3 --kin models/armold-mks-concept-v1/kinematics.json --poses src/cad/armold-mks-product-v3/gallery_poses.json --pose-check models/armold-mks-product-v3/blender/gallery/pose-check.json --out models/armold-mks-product-v3/blender/gallery
python src/cad/armold-mks-product-v3/gallery_sheet.py --gallery models/armold-mks-product-v3/blender/gallery --poses src/cad/armold-mks-product-v3/gallery_poses.json
```

## 동작 영상 — 한 바퀴 · 자세 이동 (2026-10-27 추가 · 비작성자 검수 없음)

사용자 「작업할거 계속 이어가」(직전 제안 = 한 바퀴 도는 영상 · 관절이 움직이는 영상). 형상 · 관절 거리 · 커밋된 `.blend` 는 그대로다(장면을 읽기만).

- `blender/motion/turntable-brand.mp4` · `turntable-swap.mp4` — 표시 자세를 카메라가 한 바퀴(8 초 · 24 fps · 1280 × 720 · 조명이 카메라와 함께 돌아 빛이 같음 ·
  줌 고정). `motion-brand.mp4` · `motion-swap.mp4` — 표시 자세 → ㄱ 자 대기 → 위로 뻗기 → 손목 비틀기 → 옆으로 뻗기 → 아래 집기 → 표시 자세(계획 16.75 초 ·
  마지막 자세까지 403 프레임 = 영상 16.79 초 · 관절 공간에서 부드럽게 `3u² − 2u³` · 모든 관절이 같이 출발 · 도착 · 카메라는 방향 · 렌즈 고정으로 로봇을 부드럽게
  따라감). brand = 흰 몸체 · swap = 회색 몸체.
- 곁의 `*.json` = 출처(입력 sha256 · 프레임 검사 결과 · 프레임 JPEG 마다 sha256 · 인코딩 설정 · ffprobe 확인) · `*-strip.jpg` = 프레임 여덟 장.
  프레임 JPEG 와 프레임별 기록(`frames.jsonl`)은 작업 뿌리에만 있다 — 저장소만으로는 프레임 하나하나의 검사를 다시 볼 수 없다.
- 계획 = `src/cad/armold-mks-product-v3/motion_plan.json` · 경로 = `motion_path.py`(파이썬 표준만 — 검사기와 블렌더가 같은 값).
- **`blender/motion/path-check.json`** — `path_check.py` 가 자세 2509 개(이동을 프레임의 8 배로 나눈 2502 + 머무는 구간 시작 7)마다 `pose_check.py` 와 같은 판정(커밋된 STL · 다른 링크 바디 쌍의
  겹친 부피 ≤ 0.05 mm³ · 이웃 아닌 링크 꼭짓점 거리 ≥ 2 mm(근사) · 바닥 위 ≥ 5 mm · 관절 ±170 도 안 · 바디 메시 47 개가 닫힘): **모두 통과** · 겹침 최대 0.024 mm³(접촉면
  분할 오차 수준) · 바닥 여유 최소 34.3 mm · 이웃 아닌 링크는 어느 샘플에서도 꼭짓점 10 mm 안으로 오지 않음 · **샘플 사이 꼭짓점 이동 최대 4.54 mm**(샘플 사이는
  검사하지 않음 — 그보다 얇은 틈을 지나치는 충돌은 놓칠 수 있다). 한 바퀴 영상의 자세(표시 자세)도 같은 기록의 `turntable` 줄에서 같은 판정으로 통과.
  기록에 입력 sha256(STL 47 · bodies.json · 기구학 · 계획 · 자세 · 검사 코드)이 있고(검사 시작 · 끝이 같아야 통과), 블렌더 · 묶기 단계가 지금 파일과 같은지 ·
  밀도가 per_frame ≥ 8 · 샘플 사이 이동 ≤ 5 mm 인지 대조한다. 렌더한 프레임의 자세는 모두 이 샘플 중 하나다(블렌더 스크립트가 확인).
- **장면 고정**: 렌더 · 게시는 `src/cad/armold-mks-product-v3/motion_scene_pin.json` 의 sha256 인 .blend(MP7 에서 `blender_scene.py` 가 만들고
  `blender_verify.py` 가 확인한 이 폴더의 `kmjh-arm-v3.blend`)로만. .blend 를 다시 만들면 C7 · C7v 를 통과시킨 뒤에만 그 값을 바꾼다.
- 렌더 전 장면 확인(고정 위의 이중 방어 · 하나라도 어긋나면 아무것도 쓰지 않음): 객체 종류 수 · 빈 객체 인스턴스 없음 · 바닥 = 모디파이어 없는 사각형 ·
  배경 장면 · 재질 덮어쓰기 없음 · 카메라 원근 · 렌즈 이동 0 · 바디 47 의 이름 · 링크 · 역할 = bodies.json · 점 · 삼각면 · 감김 = 바디 STL · 모디파이어 ·
  모양 키 없음 · 렌더에 보임(객체 · 컬렉션 · 뷰 레이어의 숨김 · 제외 · 홀드아웃 · 간접 전용 · 카메라 광선 끔 · 그림자 받이 아님) · 재질 = 역할의 재질 하나
  (Principled 가 표면에 바로 · 기본색 · 알파 연결 없음 · 알파 1). 합성 · 시퀀서는 끈다.
- 프레임마다: 모든 꼭짓점 = 표시 자세 점을 v1 축으로 돌린 값(≤ 2e-6 m) · 로봇 상자 꼭짓점이 모두 화면 안 · 클립 범위 안 · 카메라 광선(64 × 36 · 렌더에 안 나오는
  객체 제외)에 로봇 · 몸체 · 남색 바디가 보임(민트는 요구하지 않음) · 파일 sha256. 끝나면 실행 중 입력 · path-check · 스크립트 · .blend 가 바뀌지 않았는지 본다.
- `motion_encode.py` 는 저장소의 정본 입력 · 정본 설정(1280 × 720 · 32 샘플 · JPEG 90)으로 지금 코드가 고정 장면에서 렌더한 프레임만 받는다: 입력 · .blend ·
  path-check sha256 · 고정 표시 · 렌더 스크립트 · 가드 sha256 · path-check 재판정 · 검사 목록 · 프레임 수(계획으로 다시 낸 수) · 프레임 sha256 을 대조한 뒤
  묶고, ffprobe 로 코덱 · 제한 범위 · 크기 · 프레임 수 · 속도 · 길이를 확인한다. 산출 이름은 `<video>-<scheme>.mp4` 로 고정 · 셋을 작업 뿌리에서 다 만든 뒤
  옛 셋을 지우고 옮긴다(곁 기록이 마지막). 밀도 · 설정 값은 `motion_path.py` 한 곳.
- 양성 대조 = `.dev/product-v3-evidence/motion-controls.json`(`run_motion_controls.py` · 63 경우 모두 통과 — 겹침 판정(닫히지 않은 메시 · 겹침 · 근접 · 바닥 ·
  관절 범위를 **하나씩** — 실패한 샘플마다 그 갈래 하나만 거짓인 경로 넷) · 검사 기록(낡은 / 실패한 기록 · per_frame 만 / 이동만 성긴 기록 · 격자 밖 계획 ·
  한 바퀴 자세 없음 · 샘플 줄을 손댄 기록) · 장면 고정(고정 아닌 .blend 거부 · 고정을 풀면 기록에 표시) · 프레임 줄 검사(바닥을 카메라와 로봇 사이로 올린
  사본 → 13 프레임 모두 BAD · 자세 · 화면 안은 통과하고 가시성만 떨어짐) · .blend 사본 열넷 · 세로 화면 · --scratch-root 없음 · meta 없는 기록 · 이어 하기 ·
  설정 바꿈 · 끊긴 / 깨진 기록 줄 · 일부만 렌더 · 묶기 전 검사 스물(「다른 입력 · 코드 · 설정」 갈래는 거부 목록이 정확히 그 항목 하나인지까지)).
  대조하지 못한 갈래와 그 까닭은 그 파일의 `not_covered`.
- 2026-10-27 독립 읽기 전용 검토(Claude 하위 에이전트 워크플로 · 같은 모델 계열 — Codex 비작성자 검수가 아님): 1 회 확인 지적 16 · 2 회 22 · 3 회 minor 4 +
  note(모두 minor 이하 · 산출 결함 없음 — 모두 검사 장치). 3 회의 「다른 .blend 로 바꾸면」 부류는 하나씩 막는 대신 장면 고정으로 닫았다. 5 회(커밋 전 ·
  문서 수치 대 기록 · 처분 반영)는 minor 1(대조 없는 갈래가 목록에도 없음) → 세 파일의 거부를 전부 대응시켜 대조를 더하거나 까닭과 함께 적음. 경과 · 처분 =
  `.dev/product-v3-evidence/motion-review.md`.
- **보기용이다**: 속도 · 가속 · 토크 · 실제 관절 범위 · 케이블은 보지 않았다. 실제 모터 궤적이나 URDF 시뮬레이션을 대신하지 않는다.

```
python src/cad/armold-mks-product-v3/path_check.py --model models/armold-mks-product-v3 --kin models/armold-mks-concept-v1/kinematics.json --poses src/cad/armold-mks-product-v3/gallery_poses.json --plan src/cad/armold-mks-product-v3/motion_plan.json --out models/armold-mks-product-v3/blender/motion/path-check.json
blender --background --factory-startup --python src/cad/armold-mks-product-v3/blender_motion.py -- --video motion --scheme brand --frames <작업 뿌리>/frames-motion-brand --scratch-root <작업 뿌리> --blend models/armold-mks-product-v3/blender/kmjh-arm-v3.blend --model models/armold-mks-product-v3 --kin models/armold-mks-concept-v1/kinematics.json --poses src/cad/armold-mks-product-v3/gallery_poses.json --plan src/cad/armold-mks-product-v3/motion_plan.json --path-check models/armold-mks-product-v3/blender/motion/path-check.json
python src/cad/armold-mks-product-v3/motion_encode.py --frames <작업 뿌리>/frames-motion-brand --scratch-root <작업 뿌리>
python src/cad/armold-mks-product-v3/run_motion_controls.py --scratch-root <작업 뿌리>
```

## 블렌더에서 관절 돌려 보기

`blender/kmjh-arm-v3.blend` 를 열면 `JOINT_J1` … `JOINT_J6` 빈 객체가 있다. 각 빈 객체의 **Z 회전만** 풀려 있고(X · Y · 위치 잠금) Z = 그 관절 축이다.
- **회전 0 = 표시 자세**(v1 의 pose_deg). 그 관절 아래 링크가 함께 돈다.
- **기하 영점(q = 0)** = Z 회전을 `−pose_deg`(빈 객체의 사용자 속성 `pose_deg`)로 — `render-zero-pose.png` 가 그 자세다(검사 C7 가 v1 길이로 낸
  q = 0 순기구학과 관절 원점 · 축이 같음을 확인).
- 보기 · 렌더용이다 — 관절 범위 · 질량 · 충돌 모델이 없고 **URDF 를 대신하지 않는다**. 회전 시험은 운동학 검사이지 충돌 검사가 아니다.

## 검사 (모두 참 — `validation.json` · `blender/scene-report.json` · `blender/verify-report.json`)

- C0 지금 native · STL 47 = 생성기 출력(sha256 묶음) · 간섭과 평가를 검사기가 지금 native 로 새로 냄.
- C1 관절 = v1(SolidCraft 관절 목록 · native 문서의 관절 snap 둘 다) · C1a v1 길이 · 축 · pose 로 다시 낸 순기구학 = kinematics.json · C1b 회전체 무게중심이 그 관절 축 위 · C1c native 구조(컴포넌트 · 발생 · 관절
  사슬) · 바디 이름 · 소속 · 역할 = **검사기가 따로 만든 정답표** · C1d 링크 좌표 범위(모듈 축 범위 · 드럼 · 캔 반지름 · 막대 0 … 165 등 98 항목 · rev1 은 돌기 셋을 더해 101) = v1 · v2 값 0.01 mm(rev1 돌기 = 그리퍼 규격) ·
  **C1e 바디 47 개 모두 검사기가 v1 · v2 값으로 따로 만든 기대 형상과 양방향 표면 거리 ≤ 0.03 mm**(관측 최대 0.0085 mm · rev1 의 공구 둘은 그리퍼 parameters · 원장 값으로).
- C2 표시 자세 정확 커널 간섭: 응답 완전(미검사 · 예산 초과 · 잘림 없음) · 서로 다른 링크 0 · C2b 사선 · 덮개 · 글자가 어떤 바디에도 묻히지 않음.
- C3 v1 모터 · 드라이버 · 커넥터 가정 상자 18 개가 모듈 안 100 %.
- C4 보호 폴더(v1 개념 · v2 산출 · v2 생성기) 모든 파일 = 시작 기준선(sha256 `35ca6f30…`) · v2 추적 파일 = HEAD.
- C5 native 에 저장된 색 = 브랜드 색(바디 47) · C6 STL = native(상자 · 무게중심 0.002 mm · 체적 · 넓이 0.2 %) · C6b 글자 · 사선 · 막대 체적 = 독립 계산
  (평면 바디 1e-6 · 허브 덮개 원판 셋 2e-4 — native 평가 체적이 곡면 분할 값).
- C7 블렌더: 바디마다 STL 점과 점 하나하나(가져온 직후 · 부모 뒤) · 삼각면과 감김 = STL · 부모 · 잠금 · 재질 슬롯 · 면 색인 · 색 값 · 관절 빈 객체 ·
  모든 꼭짓점 ±10° · 조합 자세 · 기하 영점 · 렌더마다 카메라 광선으로 로봇 · 흰 몸체 · 글자가 보임. C7v .blend 다시 열기 · GLB 다시 가져오기 — 바디마다
  STL 점 · 삼각면(감김) 대조 · 색 · 메시 이름 목록(바디 47 + 바닥).
- 양성 대조(일부러 넣은 잘못을 목표 검사가 잡는지) = `.dev/product-v3-evidence/controls.json`(**MP7 · rev0 실행 기록 그대로**) · rev1 에서 다시 돌린 공구 대조 여섯 + 가드 = `controls-rev1.json`(따로 · 코드 sha 함께).
- 모든 쓰기는 `guard.py` 로 v3 산출 · v3 근거 · 격리 작업 뿌리(표지 파일 · git 밖)만 — 파일 하나하나까지.

**검사 범위 밖**: 표시 자세 · 갤러리 정지 자세 7 개(`blender/gallery/pose-check.json`) · 동작 영상 경로의 샘플 자세 2509 개(`blender/motion/path-check.json`)
말고 다른 자세, 샘플 사이의 연속 움직임과 여유, 강도 · 하중, 실제 모터 치수(MKS 는 도착했으나 아직 재지 않음 — v1 가정값).

## 다시 만들기

```
python src/cad/armold-mks-product-v3/build_product.py --cli <solidcraft-cli.exe>
python src/cad/armold-mks-product-v3/validate_product.py --cli <solidcraft-cli.exe>
blender --background --factory-startup --python src/cad/armold-mks-product-v3/blender_scene.py -- --model models/armold-mks-product-v3 --kin models/armold-mks-concept-v1/kinematics.json --out models/armold-mks-product-v3/blender
blender --background --factory-startup --python src/cad/armold-mks-product-v3/blender_verify.py -- --blender-dir models/armold-mks-product-v3/blender --model models/armold-mks-product-v3 --kin models/armold-mks-concept-v1/kinematics.json
```

겉모양 치수는 `src/cad/armold-mks-product-v3/parameters.json`(관절 거리와 무관한 값만 — 보호 키는 C1d 가 v2 와 같은지 본다 · rev1 공구 끝 돌기 · 구멍은 그리퍼 · 원장 규격과 한계(바닥 살 · 돌기 · 모따기 · 재료)를 본다).
