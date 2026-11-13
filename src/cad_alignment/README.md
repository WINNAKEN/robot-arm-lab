# v2 CAD 정적 관절 대조

승인된021 코어의표시자세와v2파일에저장된6관절의원점·축·0각표지를대조한다.
모델링/CAD·펌웨어는수정하지않는다. `flip`에서native양의회전방향을추정하지않는다.

저장소루트:

```powershell
py src/cad_alignment/test_alignment.py
py src/cad_alignment/run_checks.py
py src/cad_alignment/alignment.py build
py src/cad_alignment/alignment.py verify
```

결과는 `outputs/v2-joint-alignment/runs/<current run>/report.md` 및 `report.json`.
immutable과거스냅샷이므로사용전verify한다. currentPASS는생성무결성이며독립수용처분은
`.dev/cad-alignment-evidence/disposition.md`에둔다. 미검토021재생성본은기존publicverify가
PASS여도고정된승인baseline/receipt/core핀을통과하지못하면거절한다.

검사대상은solidcraft/31/mm,7개world-root/identity occurrence,6revolute joint의
저장anchor/axis/zero와6개joint.as_built command다. 저장원점오차≤1e-5mm,
축성분오차≤1e-8. 지원형식밖transform은거절한다. 이는기계가공공차가아니다.
snap보조x는관절프레임방향이며수학코어의링크R_child와동일하지않다.
링/body/features/캐시형상은해석하지않으므로파일전체해시일치가형상검증은아니다.

표의기하0각은canonical코어입력이다. CAD native에그각을명령하는것은아직검증하지않았다.
native양부호/solver/runtime/링크body자세·실물영점/모터부호/감속비/한계·TCP·Isaac는미검증이다.
링indexed-geometry는020미해결백로그그대로다. CAD앱이나모터를실행하지않는다.

입력JSON/ZIP→typed immutable record→대조순서이며저장가능한일반실패는FAILED로끝내고
원예외를재전파한다. singlewriter전제,저장불가/강제종료시과거current가남을수있어
build실패를기준으로중단하고저장복구후재생성해야한다. 저장내구성보장은아니다.
