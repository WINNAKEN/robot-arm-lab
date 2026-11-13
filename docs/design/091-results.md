> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 091 — 고정 기저 표현 수정 후보의 사전장면 검증 연결 실패

2026-10-31 KST. 사용자 COM불일치원인파악·수정·큰동작지시에따라새고정기저RootAPI수정후보를구현했다. HOST14그룹310·비작성자L2R1/L4R1 PASS9/0, 독립root27/balance34/floating21 및추가원자료경계검사PASS였다. 이것은실제RootAPI수정성공수용이아니다.

## 실제 실행과 최초 오류

새import `e0c7d1c1ce8d4f44be55cd7ca916deee` IMPORT_VERIFIED/child0. smoke `88670c028b6a4cb8b63a6db3d0e15f0e`는161.532초·child1/REAPED·timeoutfalse로실패했다. 원terminal/failure.txt의최초원인은 `ValueError: all source colliders including floor`다. scene415의before-scene용verify_import호출이기존import전용check_colliders의floor=False기본문맥을사용했다. stage에는이미floor포함12collider가있고검사는11개만기대했다. 이는작성자가추가한연결부결함이다.

실패는RootAPI이동전에발생했다. base-before.usda만저장됐고base-after/report/PNG/긍정physicsstep은없다. 따라서고정기저파싱수정·fixed9·원COM일관성·큰동작은아직실제수용되지않았다. 원consumer의sdk_connected:false는예외시생성되는일반FAILED필드이며SDK미시작의증거가아니다. child-started/sdk/provider/원로그가실제시작을보인다. 원자료를수정하거나실패를통과로바꾸지않았다.

첫진행조회에서아직없는dynamics표본을인덱싱한읽기관측오류가있었다. missing을null로표시하도록조회만교정해원실행을다시읽었고SDK를재시작하지않았다. 이는native첫오류와별개다.

## 처분과 연속 계보

091의원장import1/smoke1/motion0을종결하며원02:54:30Z종료/02:39:30Z발사마감을변경하지않는다. 동일091 SDK추가실행은없다. 고정루트표현가설과원089 COM실패·과거소진/임계는보존한다. 실물CAN/급전/flash/보정/모터/설치/재부팅/학습은없고hardware_approved=false다.

사용자의남은명시목표를계속수행하기위한092분할계획은 `092-floor-context-repair-and-motion.md`다. API에명시적floor문맥을추가하되기존import는false그대로,이번scene만true로12개전체를검증한다. 바닥삭제·필터링·기준완화를하지않는다. 091부터의전체L2/L4/class원장은이어지며새폴더로리셋하지않는다. 현재same-family비작성자공통편향과이번누락된실제scene문맥검토한계를명시한다.
