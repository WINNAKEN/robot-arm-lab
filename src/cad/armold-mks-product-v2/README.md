# armold-mks-product-v2 — 1:1 제품 외장 v2 · J2 첫 분할 (MP4 · 계획 `docs/design/014-product-exterior-v2-display-kit.md`)

v1 개념 모델(`models/armold-mks-concept-v1/` — 동결)의 기구학을 그대로 쓰는 1:1 외장(A2)과 J2 모듈의 부품 분할(A3)을 SolidCraft 명령 스크립트로
만든다. 산출물 = `models/armold-mks-product-v2/`(A2) · `models/armold-mks-product-v2/j2-split/`(A3). 근거(실행 결과 · 표준 출력 · 오류) =
`.dev/product-v2-evidence/`.

| 파일 | 무엇 |
|---|---|
| `parameters.json` | 외장 치수(캔 반지름 · 끝 덮개 · 색 띠 · 관절마다 출력 쪽) · 링크 모양 · J2 분할 치수(`j2_split` — 끼움 값은 시험편 판정 전 가정) |
| `v2geom.py` | 형상 라이브러리 — `Spec`(v1 기구학 · 치수 읽기) · `Frame`(관절 좌표) · `Builder`(SolidCraft 명령 쌓기 · 관절 모듈 · 링크 · 관 · 둥근 기둥 · 회전체 · 모서리 둥글림) |
| `build_product.py` | A2 조립(native · STEP · 3MF · 그림 셋 · v1 ↔ v2 나란히) |
| `validate_product.py` | A2 검사 일곱 → `validation.json` |
| `build_j2_split.py` | A3 J2 분할(부품 여섯 · 참조 다섯 · A2 의 자식 링크 허브와 관 · 검사용 A2 외곽) + 만들기의 검사 다섯 → `j2-split/split.json` |
| `check_j2_split.py` | A3 의 검사 다섯 더(닫힘 · 셸 · 가정 상자가 캔 속 · 최소 벽 · 자리파기 틈 · 출력 방향) → `j2-split/validation.json` |

## 돌리기

```powershell
$cli = "C:\tools\SolidCraft-0.18.2\solidcraft-0.18.2-windows-x64-portable\solidcraft-cli.exe"
& C:\projects\printforge\.venv\Scripts\python.exe src\cad\armold-mks-product-v2\build_product.py --cli $cli
& C:\projects\printforge\.venv\Scripts\python.exe src\cad\armold-mks-product-v2\validate_product.py --cli $cli --model models\armold-mks-product-v2 --evidence .dev\product-v2-evidence\check
& C:\projects\printforge\.venv\Scripts\python.exe src\cad\armold-mks-product-v2\build_j2_split.py --cli $cli
& C:\projects\printforge\.venv\Scripts\python.exe src\cad\armold-mks-product-v2\check_j2_split.py
```

- 파이썬은 PIL · trimesh 가 있는 것(이 PC 에서는 PrintForge 의 가상 환경)을 쓴다. SolidCraft 는 `SOLIDCRAFT_GPU=cpu` 로 부른다(스크립트가 넣는다).
- J2 분할의 만들기는 정확 커널 간섭 검사 때문에 이 PC 에서 약 4 ~ 5 분 걸린다.
- 치수를 바꾸면 `parameters.json` 을 고치고 위 넷을 다시 돌린다. v1 파일은 고치지 않는다(`validate_product.py` 가 해시로 본다).
