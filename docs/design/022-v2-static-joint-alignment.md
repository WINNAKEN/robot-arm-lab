> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 022 — v2 CAD 정적 관절축·영점 대조

사용자 승인: v2 CAD 관절축/영점을021코어와 대조하고 부품도착 전 검증한다. 링형상은계속보류한다.021은동결수용된수학후보이며수용범위를자동확대하지않는다.

## 범위

`src/cad_alignment/` 새 stdlib 비교기와 시험,`outputs/v2-joint-alignment/` 새 결과를 만든다. 원본CAD/펌웨어/021·020소스와current는수정하지않는다. 실제CAD앱/모터/플래시·Isaac실행/구매없음. CAD파일을읽는것은모델수정이아니다.

입력은 v1kin, v2 native `.solidcraft` ZIP의유일한document.json, v2 build-commands.json, 실제021코어와공개verify로확인한현재021run이다. ring features/params/validation.checks는해석하지않는다. ZIP전체파일해시는형상검증이아니다.

### 승인된021 의존성 admission (L2R1 지적022-R1-1 수용)

verifyPASS는생성무결성이지독립수용이아니다. 비교기는현재독립수용된021기준(bff5ff0)의다음실제bytes해시를상수로핀한다:
- `.dev/joint-frames-evidence/frozen-r2-manifest.json`: `43d1153d75917a96e8ded6f313e4314846766f8cbb67f818670b095c41ff8422`
- `.dev/joint-frames-evidence/l4-r2.md`: `fdd4030257d77b51e9077d1e8cbd1425dd036a70f9ffa4be13ae96e3ba5f5138`
- 실제import하는`frames.py`: `1eb5d41f439e5201ce0b0c5ee53222584082b8446bfef2e00a5bdd3eed5b4d46`

admission은두근거파일의핀을먼저검증하고manifest9개경로(기존계획/4소스/acceptedcurrent/해당run3파일)의실제해시를검사한다. 실제로드하는core파일도핀에맞아야한다. 이후에만021verify를호출한다. acceptedrun은9921dbd274204f93956849385affe980이며새021생성이나source/approval기록수정은거절한다. 로컬승인된기준의동일성검사이며외부서명/악의적저장소수정방지주장은아니다.

022manifest에이의존성핀/현재021run을넣고022verify에서도재검사한다. source와새021producer/current를함께고쳐021verify가통과하는반례,receipt또는baseline핀변조,실제importcore변조를반드시거절하는시험을추가한다. 이지적은새dependency-admission class최초로기록하며이전class와혼용하지않는다.

## 정적 수용 계약

- supported solidcraft/31,mm,7component(Base,Link1..6),7occurrence,world-root parent0/identity4x4transform,Base만grounded. id정수(bool불가)/고유성/component참조/이름/부모자식순서를검증한다. 이정적형식밖은unsupported로거절하고일반변환추정하지않는다.
- native assembly.joints6개는고유name/id,kindrevolute,chain Base:1→Link1:1→…→Link6:1. name Jn_DISPLAY_ZERO,양쪽snap point/origin·unit z,childsnap unit x⊥z를검증한다. snap x는관절프레임의보조방향이며core링크자세R_child로동일시하지않는다.
- angle0rad,values[0],offset0을명시검증한다. flip은bool,현재저장값을보고하되양의native명령부호를추정하지않는다. native limits2숫자rad와command limitsdeg를일치검사하나실물한계로수용하지않는다.
- build commands의모든entry는object/command문자열/params객체를먼저검증한다. joint.as_built6개의name/type/a/b/at.point/z/limits를검증한뒤native와대조한다. 다른command params는envelope만검증하고형상내용은제외한다.
- core.decode+fk(delta0)의각origin/axis와native양snap+command를대조한다. 위치허용오차1e-5mm,축성분1e-8,각도0은1e-10rad. parent회전전치로native월드축/상대원점을역변환해core axis_parent/offset_m도대조한다.
- native0=canonical delta0=기존displaypose의 **정적기준연결만** 수용한다. geometric0에대응하는canonical각은-display_pose_rad로표시한다. native명령에그각을넣으면geometric0이라는주장은하지않는다. 실제native양부호/flip solver/다축구동·링크body자세는별도runtime검증대상이다.

## 입력·상태 경계

JSON은021의bounded parse와형식검증helper사용,소비필드를frozen dataclass로바꾼후대조한다. kin/commands각1MiB,nativeZIP8MiB/document1MiB,JSONdepth64;ZIPdocument중복·압축방식stored/deflated외·암호화거절. header/중첩형식/수치가틀리면일반실패로끝낸다.

새build는입력읽기전BUILDING,고유run에입력snapshot/결과/manifest저장,producer(비교기+실제frames.py)/입력/021current해시고정. 최종verify후만성공flag,unsuccessfulfinally는FAILED/reason+원예외재전파. 검증기는currentPASS/run/manifest/payload/입력/core/021dependency동일성을읽기전용확인,과거fallback없음. 단일writer,저장불가/강제종료durability보장밖. canonical021build를부수효과로호출하지않는다.

## 시험·검토 예산

- 첫검토전L2최대2/L4최대2선언. repo규율대로비작성자검토,작성자가수정한다. 외부계열NOT_RUN은기존중앙도구차단기록대로잔여위험유지/우회없음.
- 소비native/command객체·배열·leaf의누락/다른kind/shape변형과숫자overflow/ZIP중복·99압축·암호화·JSONdepth/parse를실제build→FAILED로시험한다. 예상밖ArithmeticError/중간소스변경/no-fallback/결과·core/dependency변조도검사한다.
- 각관절원점/축반전/연결교환/angle·values·offset/transform/grounded/limits변형을거절한다. 허용오차안쪽양성/바깥음성대조. 원점/축/영점검사를각각삭제하는compiled행동변형은반례가통과해시험이실패하는지확인한다.
- 기존020두EXHAUSTED class(terminalfailure/nativeindexedgeometry)·다음추가독립실측수용재발1개면EXHAUSTED임계유지. 링class는미해결보류이며범위제외로폐쇄하지않는다.021math도메인원장과firmware first-fault임계도그대로다. 새번호로reset/동일class직렬수리하지않는다.
- 103보호CAD/펌웨어+020/021동결파일의전후해시,원본CADbytes불변을확인한다. PASS후정적대조결과/각관절표/미검증항목을보고·인계하고scoped로컬commit,push없음.
