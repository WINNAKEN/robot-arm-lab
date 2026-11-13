# Armold 타입 MKS 6축 — 1:1 제품 외장 v2 (MP4 A2 · 2026-10-23) — 「L4 R2 검수 — 배송 가 · 실물 판정 전」

MP3(v1) 개념 모델의 기구학을 그대로 두고 겉모양을 제품처럼 다시 그린 1:1 외장입니다. 모터 · 드라이버를 관절 모듈 안에 숨기고, 둥근 드럼 · 모터 캔 ·
주황 띠와 끝 덮개 · 원판과 관으로 된 링크 · 둥근 베이스를 둡니다. **외곽 덩어리(속이 찬 몸체)이며 제작 도면이 아닙니다** — 벽 두께 · 속 공간 ·
체결 · 베어링 · 감속기는 다음 단계(J2 첫 분할 = `j2-split/`, 나머지 = 계획 014 의 B)에서 나눕니다. 계획 = `docs/design/014-product-exterior-v2-display-kit.md`.

- `armold-type-mks-product-v2.solidcraft`: 편집 이력 있는 native — Base + Link1…Link6 의 7 링크 · revolute 6(관절 0 = 표시 자세 `[15, -50, 70, 15, 25, -10]`도 ·
  ±170 도는 예시) · 바디 31. STEP · 3MF 는 형상만.
- `iso.png` · `front.png` · `right.png` · `v1-v2-side-by-side.png`(왼쪽 v1 · 오른쪽 v2 · 같은 iso 방향 · 각자 화면 맞춤).
- `bodies.json`(바디 → 링크 · 색 역할: body 흰 · accent 주황 · dark 진회색) · `build-commands.json` · `validation.json`.
- 「제품 외관」 의 판정은 사용자의 눈입니다(그림 · GUI).

## 기구학 · 배치

관절 원점 · 세계 축 · 링크 회전은 `models/armold-mks-concept-v1/kinematics.json` 그대로입니다(축 Z–Y–Y–X–Y–X · 어깨 96 + 78 · 상완 165 · 전완 140 ·
손목 78 / 140 mm). 관절마다 모터 캔의 쪽(캔 반지름은 여섯 모두 39 mm):

| 관절 | 축 | 드럼 지름(v1) | 출력 면 | 모터 캔 |
|---|---|---|---|---|
| J1 | Z | 90 | +Z | −Z(베이스 기둥 안 · 끝 덮개 없음) |
| J2 | Y | 104 | +Y | −Y |
| J3 | Y | 90 | −Y | **+Y**(v1 은 −Y — 전완을 상완 반대쪽에 두려고 뒤집음 · UR 같은 옆 오프셋) |
| J4 | X | 78 | +X | −X(전완 관을 겸함) |
| J5 | Y | 78 | +Y | −Y |
| J6 | X | 78 | +X | −X(손목 관을 겸함) |

치수는 `src/cad/armold-mks-product-v2/parameters.json`(외장) + v1 의 `parameters.json`(길이 · 드럼 지름 · 깊이 36 · 모터 · 드라이버 가정). 바꾸려면 그 파일을
고치고 `build_product.py --cli <solidcraft-cli.exe>` 로 다시 만든 뒤 `validate_product.py` 로 검사합니다.

## 검사 (`validation.json` — 일곱 모두 참)

- 관절 원점 · 축 = v1(native `joint.list` 의 `frame_a` · `frame_b` · 원점 차 0 mm · 단위 축 성분 차 0 — native 관절을 v1 값으로 만들었으므로 그대로
  기록됐는지를 보는 검사).
- 정확 커널 간섭(표시 자세): 검사 못 한 쌍 0 · 서로 다른 링크 사이 체적 간섭 0 · 같은 링크 안의 이음 겹침 16 쌍(셈만).
- v1 의 가정 상자 18 개(관절마다 모터 · 드라이버 · 커넥터 — v1 치수 · v2 배치)가 각 관절 모듈 덩어리 안에 100 % · 다른 링크와 간섭 0. 커넥터 상자
  모서리 반지름 36.4 와 캔 39 의 차 2.6 mm 는 벽 두께가 아닙니다.
- v1 동결 파일 23 개 해시 불변(`frozen-manifest.json`).

## 아직 없는 것

케이블 통로(사용자 결정 「베이스→손목 이어진 통로」 — 다음 단계 B2 · 이 외곽이 바뀔 수 있음) · 부품 분할(J2 만 `j2-split/`) · 감속기(자리만 · 방식은 B3
에서 Mech-Sparring 비교) · 실물 모터 맞춤(MKS 2 세트 실측 전 가정) · 관절 범위 · 강도 · 하중.
