# 시작 경계를 분리한 정적 관절 비교

부모프로세스가어떤repo의존성을읽기전에BUILDING을기록한다.
검사한worker/contract를새bundle에복사해별도Python자식으로실행한다.
core누락·import실패·childnonzero/timeout·응답오류는부모가FAILED로끝낸다.
ID할당실패는run_id:null/FAILED다. stdout/stderr와실패이유를보존한다.

```powershell
py C:/projects/robot-arm-lab/src/startup_alignment/runner.py build --root C:/projects/robot-arm-lab
py C:/projects/robot-arm-lab/src/startup_alignment/runner.py verify --root C:/projects/robot-arm-lab
py src/startup_alignment/test_startup.py
py src/startup_alignment/run_checks.py
```

`--root`는필수절대경로다. 새결과는 `outputs/supervised-alignment-v1/`.
`current.json`으로현재run을찾는다. 각run의report.md는정적6관절대조표다.
PASS는생성무결성이고독립수용처분은 `.dev/startup-boundary-evidence/`를따른다.
FAILED후이전runfallback없으며입력복원만으로회복하지않는다. 명시build가필요하다.

stdlib/부모진입스크립트/정상Python과유효CLI파싱이신뢰기반이다.
부모스크립트자체의삭제/문법파손·Python시작불가·저장불가·부모kill/전원손실·동시writer는보장밖이다.
저장이불가능하면이전current가남을수있다. build가실패하면중단하고복구후재생성한다.
이제약은core/worker/contract/asset같은repo의존성누락을제외하지않는다.

동결023코드는typed수학/대조함수의내용자산으로만핀·재검증하며구build/verify/main은호출하지않는다.
asset와021core는검사한정확한소스bytes로실행하므로기존pyc를읽지않는다.
021의고정승인baseline/receipt/run을확인한다. 구023current REVIEW_BLOCKED는그대로다.

링형상·native양의회전방향/solver/body자세·실물교정·모터/CAN/Isaac는검증하지않는다.
시험의re-pinned child fixture는임시복사프로그램용이며실제worker승인이나production핀변경이아니다.
