> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 091 — 기저 COM 불일치 원인 대조·고정 기저 표현 수정·큰 동작

2026-10-31 KST 코딩/실제 시뮬 단위. 사용자 「기저 COM 위치·속도 불일치부터 원인 파악하고 수정해서 큰 동작 시뮬까지」 지시, 실물 CAN 제외. 첫 시계02:09:30Z, 종료02:54:30Z(한국11:54:30), 새 prepare/launch는900초여유로02:39:30Z 이전만 허용한다. 새091 원장 import/render_smoke/motion 각1회·native각600초·자동재시도/자동새예산없음. L2최대2·L4최대3(코드수리와실제자료사후감사포함), 기존089/090종료예산을재사용하지않는다. 의미있는변경5~9파일의M/검수급45분상한이며 나머지동결복제는원바이트보존한다.

## 원자료와 원인 가설

089 smoke 원봉인 report는 실제 fixed_base=false/M15×15, root COM0,0,.057과 root/link0 속도동일이다. 현재SDK설명은 root velocity가월드 COM 선속도라고명시한다. 물리루트는 USD `/World/Robot/Geometry/Base`의 ArticulationRootAPI이며, 별도 `/World/Robot/Physics/root_joint`가 비물리월드 `/World/Robot`에 Base를묶는다. URDF importer 설정 fix_base=true만으로런타임고정기저가확립되지않았다. 사후validator의COM차분/속도x,y불일치는원자료로재현됐다.

NVIDIA 공식 OmniPhysics articulation 문서의 USD Hierarchy/Articulation Root는 고정기저RootAPI를월드fixed joint 또는그조상에적용하고, root rigid body에적용하면floating 표현이라고규정한다. 따라서 고정월드관절의조상인 `/World/Robot`에 root API를이동하는것이우선수정후보다. 정확한원인은원USD정적분석+공식계약충돌과수정후실제fixed_base/COM관측으로판정하며, 공식문구만으로런타임개선PASS를주장하지않는다. TGS의position/velocity분리효과는별도가능성이며허용오차를늘리는근거로쓰지않는다.

출처: https://docs.omniverse.nvidia.com/kit/docs/omni_physics/latest/dev_guide/rigid_bodies_articulations/articulations.html (2026-10-31 읽기). 기존 pinned torque_api.py root transform/velocity docstrings와원USD바이트를함께대조한다. 조사정본은 `_research/091-root-com-cause.md`다.

## 구현 범위

소유는 새 `src/simulation/fixed_base_run/`, `outputs/isaac-fixed-base-091/`, 본계획/결과/원인조사와최소인계다. 08916파일을복제하되 driver의output/experiment/root/계획SHA·config의root/experiment/deadline·README/test_scene결과경로를새091로결속한다. 물리기준·제어경로/게인64/16·effortcap·질량/관성·floor/collision/중력/관절거리·입력URDF·기존SDK lifecycle은바꾸지않는다. 새root_binding.py(표현정규화/정적·런타임계약)와HOST검사를추가하고driver의닫힌source목록에도결속한다.

1. 시뮬 stage에 원import USD를reference한뒤, timeline이멈춘상태에서정확한11body/단일원root/단일월드fixedjoint/세계identity·부모관계를확인한다. PhysicsArticulationRootAPI를Base에서제거하고월드고정관절과모든robot link의조상인 `/World/Robot`에적용한다. PhysxArticulationAPI·self-collision=false도그root에적용한다. 원fixed joint/body0/body1/frame은변경하지않는다. 사실상기저구속이같은올바른articulation파싱표현을만든다. 루트선택전후관측과API·위치·불변physical입력의증거를기록하며, 예상외구조면거절한다.
2. Articulation 래퍼를새root경로로만든다. 기존SDK.observe/bind가실제root경로와소비객체를기록하므로그결속을유지한다. 초기static/FK/관성/충돌/worldanchor원검사는그대로적용한다. 원import단계는원래대로하고시뮬 stage만정규화하므로원import proof는과거와같이raw/normalized검증된다.
3. 런타임 shared_metatype.fixed_base가실제 bool true이고9DOF·M9×9/C9/G9가실제API에서나오는지강제한다. 15행렬을잘라9로만들지않는다. 기존floating15지원과반례는HOST에서보존하고실제robotfixed근거없이승격하지않는다. 고정/부유모두에서원root/link0 pose·velocity·COM·clock을읽고기존원기준(1e-4+1%)의COM차분/속도일관성을검사한다. fixed라는이유로루트자료를0으로대체하거나검사를생략하지않는다. 각실제rootpose가원Base위치/회전을유지하고root속도가원고정기준내인지추가확인한다.
4. 기존13그룹283HOST의원의미를새경로로재실행한다. 고정기저fixture에만새root관측필드를실제선언한양성으로추가한다(필수필드누락허용없음). 새root선택의wrong/multiple/rootjoint/ancestor/비정체월드/비정지거절·fixedflag/Mdimension·COM실제역행/루트움직임음성·미보정floating반례·원API배치변형을별도로검출한다. 새source/테스트·구source·입력해시동결후비작성자L4를받는다.
5. 검토통과후fresh import1→2초render_smoke1→원정착/바닥/중력/렌더기준뿐아니라수정한fixed-root관측/COM/모든9항계산원기준PASS일때만52초큰동작motion1. 관측실패·fixedflag불일치·원기준실패·시간초과면다음목적은NOT_RUN. 실제움직임까지실행된실패도원자료로보존한다. 원큰동작정착0.5도/1도초/1초를완화하거나성공할때까지튜닝하지않는다.
6. 봉인된실제PNG만로컬영상으로만들고decode/첫중끝을확인한다. 실패/성공표시를분리하고부모회수자료로성공terminal을소급생성하지않는다. 외부업로드없음. 원격소유프로세스/lock해제·소유입력불변·원089/090/과거실패·소진/임계를대조하고인계/로컬커밋으로남긴다.

## 판단 경계

새root표현에서fixed_base=true와COM일관성/9항API가검증되면현재고정robot의표현문제수정으로분류한다. 이는기존floating15관측이나moving-root독립교정을완료한것이아니다. 로봇PD·포화의유일원인/모터실물성능은여전히별도UNKNOWN이며동역학추정치를PD센서로쓰지않는다. 원089실패를새PASS로덮지않는다. 질량관성가정·자기충돌OFF·floorON·링보류·포그숨김유지.

실물 CAN/급전/플래시/보정/모터운전/구매/설치/전원정책/재부팅/학습은없음, 모든hardware/calibration승인false다. 모델링/CAD/URDF/BOM/펌웨어/090보고서파일은수정하지않는다. 표준외부리뷰bridge의기존lint차단과사용자의동일계열비작성자폴백승인은지속하며공통편향을명시한다. 작성자는최종자기검수하지않는다.
