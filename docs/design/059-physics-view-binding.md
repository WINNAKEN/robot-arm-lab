> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 059 — 단일 Lab physics view와 experimental prim 연결

사용자 「오류부분 해결하고 다시 재연결테스트 진행해」에 따라058 invalid tensor entity를수정한다. SDK원source읽기에서 Lab PhysxManager.reset은자체backend view를만들고SDKexperimental Articulation/RigidPrim은별도SimulationManager._physics_sim_view__warp를읽는다. Lab호환patch는미래import만바꾸거나신SDKcallbacks비활성시return하므로같은view가보장되지않는다. 이는원인가설이며실제before/after identity·유효성으로확인한다. 수집SDKsource 원본/해시를보존한다.

M10/45분23:00~23:45UTC, 소유plan059/src/simulation/physics_session9파일(기존session/providers/worker/settings/launch/tests/README+robot.py/physics.py), outputs/isaac-physics-v1. L2/L4각max2비작성자정적읽기검토,실행생성금지. 이전외부hook차단재시도없음/samefamilyfallback한계. provenance7/physical6EXHAUSTED/eligibility2next독립실측작성자수용1충분임계·기존0583예약SHA/nested이력보존. 새classreset주장없음,class착지예산종결비작성자판정필수. .dev/CAD/BOM/기존source무수정.

059가새process-local readiness adapter와collector연결을소유한다. 새robot은053동결내용을복사하되collect_bodies의Lab reset/play확인뒤게인조회직전adapter를호출한다. worker가cached physics.py를로드한다. SDK/Lab설치source파일을고치거나sys.modules/module class를교체하지않는다. adapter는설치source해시를고정해확인하고, 실제Lab manager가PhysxManager·CPU이고Labview가유효함을확인한다. 각prim모듈의SDKmanager참조를관측한다. SDK기본callbacks가모두비활성이고device CPU/enginephysx이며기존view가None또는Lab동일view일때만그manager의_view참조를같은Labview로연결한다. 두번째physics initialize/play/추가warmup을하지않고새view도만들지않는다. prim별기존SDK_on_physics_ready(None)를호출하고실제tensor entity유효성9개(Articulation1/RigidPrim8)·동일Labviewidentity를확인한다. live別view/활성callback/다른backend/device/유효성실패는거절한다. 불변pointer읽기같은도중엔정적OS전체attestation이아니라고정producer/PID/hash측정을신뢰한다.

모든before/after 상태·Labmanager/view ID·SDKmanager/view ID·callback/device/engine·9prim의실제type/path/valid상태와SDKsource핀을physics-binding.json에기록한다. 실패도원상태/최초오류를기록하고게인조회전FAILED로종료한다. 성공record는terminal의다섯번째hash필수artifact가되고root가같은run/job/PID·CPU/Physx·viewID관계·callbacksfalse·정확한9prim종류/path·source핀을검증해야수용한다. 이중관측표의임의ID전체재명명탐지를주장하지않는다. 다른4facet/numeric/metadata/GPU13/전후5modulebinding/actualexit/PID/hash/transport계약을보존한다. USDfallback/가드삭제/임의sleep으로대체하지않는다.

호스트기존13시험보존+fakeLabview/SDKmanager/prim을통해바인딩전게인실패→실제collect_bodies경로바인딩후게인도달positive,invalidview/foreignview/활성callback/device/prim실패negative·resealedrootartifact관계변조negative를검증한다. fake는HOSTMODEL/설치실증과구분. AST/whitespace/독립L4후새audit900/diag300/connection600각1회·원본freshproof300초로순차실행한다. 원058원장은불변으로새원장에보존하며추가실패재시도없음. readiness원인확인/로봇수용을구분한다.

실물보정/모터/CAN/플래시/설치/재부팅/전역설정/구매/학습/CAD수정없음. 질량관성가정·047미해결·링보류유지. SDK내부pointer연결은해당소유process수명에한정하며버전핀밖미지원/연결실패는정직하게남긴다.

SDK manager참조범위는 Articulation/RigidPrim과공통basePrim의모듈전역 SimulationManager를포함한다(base _on_physics_ready가device를읽는다). callback에None을주는것은설치source에서payload를사용하지않음을확인한버전한정이다. SDKdevice는설정변경하지않고Lab CPU와일치하는지검증하며불일치면실패한다.
