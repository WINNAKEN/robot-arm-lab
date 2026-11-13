> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 024 — 의존성 로딩 밖의 시작·실패 경계

2026-10-24 사용자승인: 코어누락도FAILED로끝내는별도시작경계의신선설계/구현/오프라인검증. 링은계속보류. 020/023의BLOCK·EXHAUSTED와반례는동결하며새번호로승인을승계하지않는다.

## 남은 지적에 대한 구조적 답

023은module초기화에서core존재를검색해try/finally보다먼저실패했다. 새 `src/startup_alignment/runner.py`는**정상CPython/stdlib와진입스크립트**만신뢰기반으로두고repo모듈을module-level에서읽거나import하지않는다. 유효한CLI `build --root <절대경로>`의root는파일존재검색없이받는다.

부모프로세스만새 `outputs/supervised-alignment-v1/current.json`을쓴다. try안에서출력디렉터리생성→첫BUILDING(run_id:null)→ID할당→BUILDING(새ID)순서다. **contract/worker/asset/core/입력의어떤파일읽기도첫BUILDING뒤**다. ID할당실패도writable일때FAILED/run_id:null로끝낸다. atomic쓰기의임시이름은singlewriter고정경로로ID생성에의존하지않는다.

## 부모·자식과 핀

- 새파일은runner.py,worker.py,contract.json,시험/README뿐이다. runner는contract bytes SHA를핀하고contract는worker SHA와동결023비교기asset/승인021기준의핀·입력경로/크기목록을정한다. contract/worker핀검증도첫BUILDING뒤다.
- 부모는검사한worker/contract바이트를고유attempt bundle에복사하고`sys.executable -I`로자식을실행한다. CLI root/bundle/contract는명시절대경로다. 자식timeout10초,자식stdout/stderr와exitcode를보존한다. 자식의import/syntax/누락/프로세스비정상종료는부모가실패로수용하며성공문자열만으로PASS를주지않는다.
- 자식은핀된동결 `src/cad_alignment/alignment.py`의**수학/typed대조함수만내용자산으로재검증**한다. 읽은정확한asset bytes를compile/exec해로딩한다. 구build/verify/main/current쓰기호출금지. 구source·core·CAD·020/021/023publishedcurrent는수정하지않는다. 누락core가구module초기화에서터져도부모의FAILED경계안이다.
- 자식은승인021의baseline/receipt/core/9파일·acceptedrun을검증한후현재와같은6축정적metadata대조를한다. source capture전후불변을확인해report.json/report.md와response.json을쓴다. response는scope/status/6관절/파일해시/입력해시/021dependency를명시한다. parent/child프로토콜은불완전·중복키·비유한·run불일치·잘못된scope/관절수/허용오차초과를거절한다.
- 부모는childexit0뿐아니라response·report스키마/해시·핀된입력목록과현재source/producer동일성을검증하고입력스냅샷·stdout/stderr·manifest를고유bundle에보존한다. 부모소스/contract/worker도전후해시를확인한다. public verify후에만최종successflag를세운다.
- 실패경계는**generic finally**로성공하지않은모든종료에FAILED/run_id/reason/childexitcode/진단경로를기록하고원예외를전파한다. 원인상세는부모traceback 또는보존childstderr에남긴다. 실패한status쓰기자체도nonzero이며삼키지않는다.

## verify와 보장 한계

새verify는stdlib만으로currentPASS/run/manifest/고정artifactset/입력snapshot·현재source/parent·worker·contract해시/승인021핀을읽기전용확인한다. core나023모듈을import하거나child를실행하지않는다. FAILED/BUILDING/REVIEW_BLOCKED뒤과거bundlefallback없음. 구023의BLOCK은해제하지않는다.

정상interpreter/stdlib/부모진입스크립트와유효한명령파싱을신뢰기반으로명시한다. 부모스크립트자체가삭제·문법파손되거나Python이시작하지못하면이프로그램은기록할수없다. 동시writer·저장불가·부모강제kill/전원손실의durability보장도제외한다. 저장불가때이전current가남을수있어build실패를기준으로중단해야한다. 이한계는core/worker/contract/asset누락같은**repo의존성실패를제외하는구실이아니다**.

## 실제 검증과 검토 예산 (첫 검토 전 선언)

- L2최대2/L4최대2. 비작성자검토필수,작성자가수정. 외부계열은기존중앙도구차단NOT_RUN잔여위험,우회없음.
- 전용복사root의실제CLI에서정상PASS뒤core누락/rename·worker/contract/asset누락·핀변조·입력누락/shape/ZIP오류→nonzero/새FAILED/예전run거절/명시재생성회복을시험한다. 원023CLI반례도동일한core삭제로새entrypoint에서재실행한다.
- 복사fixture의핀을명시재설정한시험용worker로실제child의syntax/import예외·exit nonzero·timeout·exit0응답누락/손상/거짓scope·잘못된관절수/해시/허용오차를주입한다. 이것을productionworker실행이라고혼용하지않고원프로토콜부모경계를시험한fixture임을기록한다. 출력경로쓰기오류/ID할당실패/최종verify오류는별도fault injection으로단언한다.
- BUILDING을worker로딩뒤로옮기기/FAILED마무리삭제/childexit검사삭제의compiled행동변형을양성baseline뒤실행해실제반례를검출한다. 단순컴파일실패나토큰존재로검증했다고하지않는다.
- 기존020/023startup/input/result-finalization EXHAUSTED 원장·다음추가독립실측수용재발1개면EXHAUSTED임계를유지한다. ring indexed-geometry EXHAUSTED/미해결보류,021math CLOSED이력,023dependency CLOSED이력,firmware first-fault binding/NOT_REACHED도유지한다. 새회차나부모/자식분리로reset하지않는다.
- 전후해시로기존020/021/023·MP5·CAD/펌웨어보존. 독립PASS후만새범위를인계하고로컬scoped commit,push없음. CADsolver/양의native부호·body/링형상·실물교정·모터/CAN·Isaac/RL·구매/플래시는포함하지않는다.
