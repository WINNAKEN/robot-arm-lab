> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 135 — v4 충돌 envelope 겹침과 원본 부품 입체의 대조

## 권한·목표·보존

2026-11-10 KST 사용자 「진행해.」는 직전 설명의 모델링 데이터 대조를 진행하라는 지시다. 실제133/05의93초 기록으로134가 찾은18 source-envelope 겹침쌍/91 양성 표본을 **같은 자세의 원본 v4 부품 메시**와 대조한다. 원고체를 기다리거나 실물을 구동할 필요가 없는 로컬 모델 검사다. 기존133/134·CAD/URDF/STL·출력 파일·인쇄 작업·실물 CAN/RS485·포트·전원·flash·설치·SSH/SDK·Drive·네트워크/시계·Git 변경0이다. 원본 모델을 고치거나 메시를 자동 수리하지 않는다.

이는완료134의수리/라운드리셋이아닌새로운원본-입체 판독 책임이다. 134의closed F1 표현/provenance 및 F2 output-root authority 계보·원시자료·예산을보존하며유사결함의새실제인스턴스는비작성자가독립판정한다. 기존동일계열비작성자폴백승인과공통편향잔여는유지한다.

소유 `src/simulation/mp18_solid_compare_135/{compare.py,solids.py,test_compare.py,test_solids.py}`4 +이계획1=M/2그룹(고정입력·실행·보고, 입체 판독). outputs/mp18-solid-compare-135/에만새결과를쓴다. Root가공유HANDOFF/SESSION만덧붙인다. 원계획이나134코드를수정하지않는다.

L1 Root → 독립L2 → 별도작성자L3/HOST → 독립L4 → Root고정핀확인·최종로컬실행1회. M내부정책상한: 작성자2700초, 주검토L2+L4합2700초(첫읽기/준비/실행/수리/출판포함,명시동결대기제외);마감예비300초. 사용자45분명시승인으로쓰지않는다. 작성자readonly준비≤120초후L2대기, FINAL L2PASS전코드0. L2/L4각max2/총4/no5. 134예산/round/EXH의이름변경초기화0.

## 고정 입력과 재현 범위

-134 F2 ef79786a074342406e7b750b476b3e41bd8a5c7f0f485a090ecdcb5410996cea, 최종L4 f8c550f17bb12ff66aa5166867bdf47737eaffb8d7fffc10c5dc1d321ea343b1/publication347ebc63f4823e92d24420a45bfc2ac8c23860ecd7be2b0e56ca7666debe5d84.
-134 Root-audit-r1/audit.json SHA1322ddfc994c9648361bcbe1bb31aa8933d0d8fb438007fa3815aa4b96fa4afc, witnesses.json SHA1d7aeb1537b08b96288235d55b0ad1b1ea196aa0560db155e234bcab34003a76, envelopes49a2f173…/pair-registryc4caa0f6…는같은134 최종artifact핀으로확인한다. 348표본중 `VERIFIED_SOURCE_ENVELOPE_OVERLAP_AT_SAMPLED_POSE`91개/18source쌍을정확히선정한다. 40UNKNOWN/미판독348214 pair-row를조용히흡수하거나검증완료로쓰지않는다.
-133 actual05 run850124eb93cc4cc4945ee02c3aa1ed0d/job816522a14e506263a7a7517ce76ad7deb23402ffc6bddd6c23513f306725a6ae, canonical native-result SHAc4345f4461601566d9398a7ab6101217f2bfa0e1f851b8bfb33352687a92b4e2/F6 3cf40c09cc20bac27195fc1963e997734f3dbc3e8e03b25bf737e0ecf97ace3f. 사용회수/모델/ledger/생성코드/메시는해당canonical/F6의SHA/bytes와실소비전에대조한다.
-원본기하는models/robot-arm-urdf-v4/asset-ledger.json의274 geometry components(PRINTED_STL111/PURCHASED_PRIMITIVE49/CABLE_APPROX114)와 meshes/{owner}.stl의원삼각형이다. body-local SI로굳혀진canonical visual STL은원본부품을순서대로concatenate한스냅샷이다. collision STL·convex hull을원본입체로대체하지않는다. 사용자현재출력중인작업파일/슬라이서/실물과의동일성은별도미확인으로기록하며,소스현재해시일치와출력작업동일성을혼동하지않는다.

## 원본 부품 대응과 좌표

고정된src/simulation/urdf_mp18_v4/assets.py의geometry_item→visual_arrays.append→save_mesh(concatenate) 순서를읽기근거로핀한다. 각owner의원본visual STL face를ledger의component순서/triangles개수로분할하고, 전274개유일ID·전체11owner·누적면수·각bounds_m를검산한다. 현재사전조사에서11링크모두면수일치. 면/정점은변형·삭제하지않고정확좌표동일정점index 통합만허용한다. source.path가실STL인항목은그해시·ledger T_link_from_source_mm→scale0.001과도대조한다. 절차형KG1 source는어셈블리메타데이터/고정producer순서·입력핀을기록하며파일이름만으로원부품을추정하지않는다. 원본CAD생성기나SolidCraft를실행하지않는다.

각134 envelope에대응하는**원component 집합**을만든다. 비-jaw whole-source envelope는해당owner의collision_included원component집합이다. jaw12는원collision STL을ledger per-part collision_hull.faces 순서구간으로나눈후,각구간의body-local vertex cloud와고정jaw_components.json의vertices_m를양방향일치검산하여source part ID를결속한다. triangle_indices는각component의local vertex-index faces이지원STL face행번호가아니므로전역face ID로쓰지않는다. component ordinal만같다고짝짓지않고전체삼각형구간·개수·경계및유일한vertex-set일치를검산한다(원좌표float32재현오차와연결한보수허용오차,사전조사목표1e-9m). 모호하거나불완전하면UNKNOWN으로남긴다. collision_excluded30개및미선정원part는범위표에서따로보이며전체v4무간섭주장을하지않는다.

91표본각각의source-pair/step/원몸체pose를원133 body_poses와대조한다. original wxyz/position은보존,작은정규화는계산에만허용한다. 원본canonical메시가이미body-local m이므로CAD변환을중복적용하지않는다. Boolean은mm로계산: 원본좌표×1000, 실제world translation×1000 및동일회전;가능하면몸체A기준상대변환으로수치규모를줄인다. 원TCP/명령targets/FK로실제pose를대체하지않는다.

## 입체 판독

이미설치된manifold3d3.5.2의Mesh64/Manifold Boolean intersection을사용한다(설치0). 입력은finite·정확vertex dedup 후watertight/winding/양의signed volume을확인한다. Manifold.status NoError,입체비어있지않음/양의부피,독립원삼각형부피와정해진수치허용오차안에서일치를필수로검산한다. 실패한import가empty가돼교차0으로통과하지못하게한다. Boolean 결과도status·finitevolume을확인한다. 입력수리/법선뒤집기/geometry weld-tolerance로형상을바꾸는조용한처리는금지한다.

각source-pair에대응하는원component들의cross-product를같은actual pose에서판독한다. 보수적original bounds로확실히떨어진part pair는별도분리근거,그외는실제원본입체교차부피를계산한다. 전체대응part pair의완전성·counts·kind·원ID·행/pose·변환·부피·상태를남긴다. 성능상같은owner-pair/step/subset을재사용할수있지만다른pose나부분집합을반올림하여동일시하지않는다. 전체91처리못하면남은것을미판독으로표시하며전체완료true를내지않는다.

판정은표본/원part pair단위다:
1. 원본printed/printed 유효입체교차>0.01mm³ → PRINTED_STL_MODEL_OVERLAP. 이것만으로설계불량/출력중단/실물충돌을선언하지않고관절·기어·장착의도확인이필요하다.
2. PURCHASED_PRIMITIVE/CABLE_APPROX를포함한양성 → MODELED_APPROX_COMPONENT_OVERLAP. 실제구매품/케이블접촉확정이아니다.
3. 유효완전한대응원part검사가전부교차empty/부피0인경우 → NO_POSITIVE_ORIGINAL_VOLUME_INTERSECTION_AT_SELECTED_POSE. 원envelope겹침은해당표본의양의부피간섭대용으로는거짓양성이지만,표면맞닿음/연속시간/미판독부품/다른시점무간섭을증명하지않는다.
4. 0<교차부피≤0.01mm³는SMALL_VOLUME_UNCERTAIN, invalid geometry·mapping·Boolean·부피검산·부족한관측은UNKNOWN. 0.01은새수치보고경계이지실물공차나이전133판정기준변경이아니다. 작은값을0으로반올림해통과시키지않는다.

공식근거 https://github.com/elalish/manifold/blob/master/bindings/python/manifold3d.cpp 및README의non-manifold input error설명. 실제설치API/docstring도핀한다. 동일Boolean커널사용자체는서로다른커널독립검증으로세지않는다.

## 실행·결과·검토

CLI는고정135 output root와제한된leaf name만허용하며arbitrary output root 인자를주지않는다. 허용authority는mutable OUTPUT_ROOT.resolve로재정의하지않고고정repo lexical 위치에결속,모든existing ancestor의native reparse/symlink를거절한다. 최초·출판직전경계를검산하고배타새leaf로쓴다. 실제소비input/source의전후핀을대조한뒤완료JSON을마지막에출판한다. 원134 F2와동일버그복원/실제root·parent·leaf junction·별칭·탈출및정상경로의실효반례는작은owned clone fixture안에서검산한다. 원133/134코드복사수정/고정입력변경은금지한다.

산출: 완료/UNKNOWN을분리한comparison.json·한국어comparison.md, original-parts와envelope→parts대응,91case와모든판독part pair/volumes,source/input manifest,재현명령. 후보의원part ID·kind·자세/시간을사용자가추적할수있게한다. 결과는원CAD수정이나SDK재실행을자동승인하지않는다.

HOST는실제producer→91선정/매핑/원본partition→Boolean→보고서양성경로와hash/run/part누락·면수순서·SI/pose·invalid/empty Manifold·Booleanerror/작은교차·출판중변경/실패·출력경계음성을포함한다. analytic hollow box/inside hole의proxy-only 겹침, containment/cube의알려진교차부피, touching·회전/단위/방향보존·근사kind구분으로판별력을확인한다.

비작성자L4는원134근거와원triangle/변환/부품대응을다른기전으로확인하고,알려진원입체부피·hollow/접함모형과실제양성의가능한내부점/ray membership·입력volume/교차교환검산을사용한다. 같은Boolean호출만재실행한것을독립기전이라고쓰지않으며커널공통리스크/실제관측누락은정직히남긴다. AC8=(1)고정권한/원본실효핀 (2)274원part/18쌍91선정및exactmapping (3)SI/실제pose (4)유효입체·volume·Boolean실패closed (5)완전한partcross-product/판정/UNKNOWN·범위 (6)실제경로양성/음성·독립관측 (7)보존/고정outputauthority/완료최후출판 (8)source·결과·예산·기존class/EXH/최종publication 일치. source4+plan1과각role누적상한·max4를지킨다. 검수자는제품patch를쓰지않는다.
