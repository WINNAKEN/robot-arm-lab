> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 124 — 새 장면을 명시적으로 비우고 실패 전 관측 보존

현재119 SDK1은실제import단계544에서FAIL,hold/small/large NOT_RUN,RGB0이다. 123raw전달은PASS이며현재첫SDK1/retry0는소비됐다. 이계획은로컬수리후보와검토만이며추가SDK권한을만들지않는다. actualnative-failure-observation.json과독립main-diagnosis가증거정본이다. caps12/7·gain64/16·velocity·0.5deg/1deg_s·34초·model을보존한다. 실물CAN/RS485·포트·전원·flash·설치·네트워크/시계설정변경0.

원인판정: context.new_stage뒤allprims[]/defaultNone라는전제를코드가검증하다실패했다. old/newroot구분과engine_before0는선행통과,engine_after0는후행이라아직미확인이다. 실제offendingprim은UNKNOWN이며기본카메라/World라는주장은아직가설이다. 원fresh-stage.json이모든assert뒤에만쓰여실패census가누락된관측결함도있다. targetinstalledsource02는SDK0/read-only이고implicitcamera가sessionlayer에있다는소스주석을확인했지만실패당시census대용은아니다.

소유: src/simulation/mp18_stage_reset_124/stage_reset.py,test_stage_reset.py,build_candidate.py,README.md 및 outputs/mp18-stage-diagnosis-124, 이계획과자기인계절뿐이다. 원119/120/121/123source·소스동결·검토·원장·markers·결과를수정/삭제하지않는다. userrepo에서다른CAD/index를건드리지않는다. 구현자는Root,비작성자검토자는기승인동일계열폴백의독립main이다(공통편향한계).

수리: fresh_stage의같은3인자함수로구현한다. oldroot/session Layer객체와현재stage의전체layerID를보관하고기존beforecensus/engine_before를얻는다. engine_before==0와finite를검증한다. context.new_stage실행직후새root/session·전체TraverseAll prims/default·engine_after_new를우선증거화한다. 새stage생성성공/oldroot와다름/새root와session이서로다른anonymous layer/두ID모두old전체layerID와다름을먼저검증한다. 이구분이하나라도실패하면Clear를호출하지않는다. 실제engine_after_new도0이어야Clear한다.

검증된새root/session 두개에만Clear를호출하여기본템플릿·session카메라·참조를제거한다. 외부layer/oldlayer/현재외부edit-target에는Clear/RemovePrim을호출하지않고설정도바꾸지않는다. root/session참조객체가여전히currentstage의동일두layer인지재확인하고, aftercensus는TraverseAll(비활성/class포함) prims[]/defaultNone,engine_after_reset==engine_after_new==engine_before==0을요구한다. 새root/session둘다empty여야하며stage전체layerstack에oldlayer가있으면거절한다. oldroot/session의ExportToString은Clear직전/직후같아야한다. 모든중간packet은검사보다앞서기록하며모든예외는error/verifiedfalse를최종기록한뒤원예외를재발생한다. 관측실패도PASS로바꾸지않는다. 이후SimulationContext가다시World/단위/upaxis/robot/floor/전용camera를원코드대로작성한다. 검사항목·guard를없애거나whitelist를넓히지않는다.

후보전달: build_candidate.py는원native.py의고정SHA42ecacda2b8bc1a1d4ed56da75abc4b5dbba3671483e4f2e8a2a762cfc7bb9d2와단일AST FunctionDef fresh_stage만대조한다. 새모듈에서그함수의실제bytes를잘라원본의해당함수구간만교체하고나머지byte불변을검산한다. 후보는own outputs/candidate/native.py와manifest에exclusive기록한다. 이스크립트는SSH/SDK/원격/원119bundle/marker를건드리지않으며가져오기만으로쓰지않는다. 후보는배포수용아님. 다음실제실행owner는승인후에만이reviewed후보를새runid/nonce/bundle/job로결속해야하며원123run재실행은금지한다.

HOST는SDK없는double로기본camera·World·중첩/비활성primitive제거,oldlayer절대무수정,재사용root/session/비anonymous/공유layer/positive·NaNclock/newstagefalse/Clear실패/관측실패/clear후재유입/primsDefault残存/oldlayer変化를음성검증한다. 후보AST교체를기계적으로대조하고변조된원본SHA/중복fresh_stage/기존후보덮어쓰기를거절한다. compile/SDK0/SSH0을확인한다. 실제USD/Kit수용과순간callback경합은HOST로수용하지않는다.

예산: source3개S1500초누적(검증예비150포함), Root책임·시계는별도기록한다. L2/L4각max2/noR3,비작성자M1200초누적(L2+L4,동결대기별도). 원123/119의source·round·과거결함/소진/예산을reset하지않는다. 새class는stage-reset-before-empty-contract및failure-census-not-persisted의구분/기존119계보착지를L2에서판정하고union으로기록한다. 반례수리는작성자가하고비작성자최종판정을받는다. 상충/미결시수용하지않고후보로보존한다.

실행·영상: 현재추가SDK0이며코드통과후구체적새실행승인이최종단계다. RGB0인이번119는movie/Drive NOT_RUN으로유지하고HOST/CAD/과거116영상으로대체하지않는다. 실제프레임이생긴승인된후속실행에만정지→small→large각gate,실제RGB MP4검산/화면검사/Drive영상+sanitizedresult업로드를적용한다.
