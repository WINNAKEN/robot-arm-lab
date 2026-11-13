# 팔 전체 분해도 — 외장 v3(rev1) + 그리퍼 KG1 (MP11 · 보기용)

이 폴더는 팔 전체 부품이 어떻게 이어지는지 보여 주는 그림이다. 치수의 원천이 아니며, 겹침 · 강도 같은 설계 검사도 하지 않았다.
계획은 `docs/design/061-arm-exploded-view.md`, 코드는 `src/cad/arm-v3-kg1-exploded/` 에 있다.

## 그림 (`renders/`)

| 파일 | 내용 |
|---|---|
| `arm-exploded-numbered.jpg` | 곧게 편 자세(q = 0)의 분해도. 번호 43 개를 달고 오른쪽에 링크별 부품 목록을 붙였다. 가려진 번호는 그림 아래쪽에 적었다. |
| `arm-exploded-home.jpg` | ㄱ 자 대기 자세(갤러리 `home`)를 앞 왼쪽 45° 에서 본 분해도. |
| `arm-assembled-home.jpg` | 위와 같은 각도의 조립 그림. |
| `arm-exploded-straight.jpg` | 번호 그림의 바탕 그림(번호 없음). |
| `arm-assembled-straight.jpg` | 위와 같은 각도의 조립 그림. |

- 점선은 관절 축(중심선)이다. 같은 점선 위의 부품끼리 그 관절에서 맞물린다.
- 관절마다 자식 링크를 그 축 방향으로 밀어냈고, 바닥에서 손끝 쪽으로 누적된다.
- 끝 덮개 · 사선 · 띠 고리 · 허브 덮개는 모듈에서 축 방향 바깥으로 뺐다.
- 로고 글자는 위팔 면에서 바깥으로 뺐다.
- 그리퍼는 서보를 뒤로, 피니언을 앞으로 뺐고, 턱 · 손끝 덮개는 양옆과 위로 뺐다.
- 벌린 양은 보기용 값이다. 개체마다 옮긴 양(mm)은 `data/render-report-*.json` 의 `offsets_mm` · `gripper_offsets_g_mm` 에 있다.

## 그린 것과 안 그린 것

- 외장 v3 장면 `models/armold-mks-product-v3/blender/kmjh-arm-v3.blend` 의 몸체 47 개.
- 그리퍼 KG1 개체 11 개.
  - 부품 STL 여섯: 바탕 · 턱 둘 · 피니언 · 손끝 덮개 둘.
  - 서보(구매품)는 상자로 그렸다.
  - 탄소 관 넷(구매품)은 원통으로 그렸다.
  - 붙인 자리는 MP9 `models/arm-v3-kg1-assembly/assembly.json` 의 `mount.g_to_world_display` 를 따른다.
  - 벌림 u 와 손끝 덮개 판은 `src/cad/arm-v3-kg1-assembly/parameters.json` 의 `gripper` 를 따른다.
- **J5 는 v3 외장 모양이다.** MP10 의 J5 실부품(`models/j5-wrist-v1/`)은 넣지 않았다. 손목 실부품 분해는 MP10 렌더에 있다.
- 나사 · 베어링 · 모터 · 감속기 속은 그리지 않았다. v3 외장은 속이 찬 덩어리다.
- 부품 목록의 한국어 이름(어깨 받침 · 손목 막대 등)은 몸체 이름을 보고 붙인 것이다. 번호 묶음은 `label_parts.py` 의 `GROUPS` 에 있다.

## 다시 만들기 · 검사

printforge venv 파이썬(numpy · PIL)과 Blender 5.2.3 을 쓴다.

```
python -I -B -X utf8 src/cad/arm-v3-kg1-exploded/make_all.py
python -I -B -X utf8 src/cad/arm-v3-kg1-exploded/check_exploded.py --write
python -I -B -X utf8 src/cad/arm-v3-kg1-exploded/run_controls.py
```

- `manifest.json` 에는 입력 · 스크립트 · 산출의 sha256 이 있다. 글 파일은 CRLF 를 LF 로 바꾼 뒤에 쟀다.
- `check.json` 의 C1 ~ C5 를 본다.
  - 입력(장면 · MP9 행렬 · 그리퍼 STL · 매개변수 · 운동학 · 자세)이 바뀌면 C4 가 거짓이 된다. 그때는 그림을 다시 만든다.
  - C2 는 그린 개체가 정답표와 같은지, 개체마다 번호가 하나씩인지 본다. 정답표는 v3 `bodies.json` 47 개에 그리퍼 매개변수로 센 11 개를 더한 것이다.
- 양성 대조는 `.dev/mp11-evidence/controls.json` 에 있다.
- 장면 파일은 열어 읽기만 하고 저장하지 않는다. 렌더 앞뒤 sha256 은 리포트의 `blend_unchanged` 에 있다.
