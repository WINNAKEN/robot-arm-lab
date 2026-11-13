> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 071 제안 — 실제 world-anchor 표현과 SDK 빠른 종료

상태: **사용자 승인 / L2 검토 후 구현·추가 native1회 실행**. 2026-10-29 사용자가 “승인할게”라고 답해 앞서 요청한 새45분 예산·추가 가져오기1회·기존 시뮬레이션/Drive 저장을 승인했다. 070의 lifecycle 수리 L4 PASS를 보존한다. 이번 사용자 목표인 최신 모델 동작·영상은 미완료다.

전체 상한은 **14:33:37–15:18:37 UTC(45분)**. source 구현은 A(S: sdk/validate,2파일)와 B(S: driver/test_host/config,3파일)를 병렬 소유하고 각25분으로 **14:58:37까지** 작성·기계검사한다. 함께 묶인5파일의 비작성자 L4는 M검수급이며 전체 상한 안에 끝낸다. 공통 L2최대2/L4최대2, 이후 native/영상·보관은 기존 설치·코드 기반 실행으로 같은 전체 상한 안에서 수행한다. source 외 실험·증거는 `outputs/isaac-gripper-v1/071/`. 이전5파일/제안 원문은 `071/original/`에 무수정 보존한다. 모델16파일·B5 동작/촬영·lifecycle070·다른CAD/펌웨어/구매는 보호한다.

## 실제 근거

070의 import run `d9f91ec76f63487295e8173d56a69b63`, job SHA `37bf34478b4f2979a14206722e44685e2be1f4748da751c0fe1670b824177437`는 최신 URDF를 실제 USD로 저장했다. 모델 USD SHA `61ca35f0ce14794d33279574494fb2ce21c22a4571c24ecaa1cdb087a107db65`. 11물리 body·11관절·11collider가 관측됐다. 검증기의 world 분류가 body0=None만 인정하여, 비Rigid 최상위 Xform을 body0로 명시한 `root_joint`를 canonical 관절에 잘못 포함했다. root/body1/Base와 양끝 identity anchor는 actual USD/snapshot에서 확인했다. 원 snapshot의 body0를 None으로 가정한 HOST 진단에서 나머지 static 검사가 통과했지만, 정식 수용으로 사용하지 않는다.

원 terminal의 최초 collector 오류는 보존됐다. 실제 extension shutdown은 약567초까지 진행됐으나 전체600초 한도 안에 종료되지 않았다. 부모는 actual child exit1/policy124/TIMEOUT/REAPED/keepawake reset을 기록했다. 정상 close 반환이나 자연 exit1을 주장하지 않는다. 기록 실패로 cleanup이 생략된 이전 결함의 재발로 귀속하지 않는다.

설치 SimulationApp 실제 소스 `070/installed-simulation-app.py.txt`의 close 주석/구현은 fast_shutdown=True일 때 빠른 종료, nonzero exit 보존, 종료 watchdog을 제공한다. 현재 start는 이를 False로 지정한다. 긴 shutdown의 독점 원인은 미확정이며 이 설정 경로와 실제 로그의 정합만 확인했다.

## 제안 변경과 수용

SDK 관측기는 원 body0/body1 관계를 그대로 보존하고 world 후보의 존재·정확한 경로·prim type·전체 applied API·활성 상태·물리 조상·full4x4 world transform·변환 time sample 수를 관측한다. None-world와 explicit-static-root를 별도 표현으로 분류한다. 임의의 “body 목록에 없는 경로”를 world로 허용하지 않는다.

허용 explicit root는 canonical Base의 실제 `/Geometry/Base` 배치에서 유도한 그 로봇의 root Xform 하나다. 실제 import의 default root 및 simulation의 `/World/Robot` reference 배치를 각각 고정 정상 대조한다. 두 고정 배치 이외의 임의 비Rigid 경로를 허용하지 않는다. root와 모든 실제 조상 prim은 비Rigid/비Mass, 활성 static Xform 또는 Scope여야 한다. USD pseudo-root는 물리 prim이 아니므로 실제 조상 목록에서 제외하되 그 지점까지의 정확한 경로 연속성을 검사한다. 현재 지원은 identity world matrix·scale1·shear0·time sample0으로 제한한다. 추가 world joint, 다른 target, 누락 target, body1 변경, 물리 조상, 동적 root는 거절한다.

fixed joint의 실제 활성 상태를 기록하고, 실제 root world matrix×local0와 Base world matrix×local1의 위치·회전 closure 및 canonical Base pose를 대조한다. source URDF나 USD를 None 표현으로 다시 쓰지 않는다. 가정 물성·조인트 거리·mimic·모델16파일·B 동작 프로그램은 그대로다.

world 제약 양끝에 같은 local 위치·회전 gauge를 적용해 실제 Base 고정 관계가 같으면 기존과 같이 허용한다. 이는 source에 없는 world joint의 표현 동등성이며 별도 공통-gauge 양성으로 고정한다. 한쪽 anchor만 변형한 위치·회전은 거절한다. root/조상 full world matrix는 계속 identity로 제한한다.

정상 대조는 기존 None-world, 실제 explicit-root, simulation reference-root다. 고정 음성은 unknown path, missing target, root RigidBody, root Mass, physical ancestor, translation/rotation/scale/shear, time-varying root, disabled joint, wrong body1, extra/missing world joint, local0/1 위치·회전, actualUSD와 snapshot 불일치다. 각각 JSON/asset 지문을 정상 재봉인한 뒤 의미 검사에서 거절한다.

SDK start는 실제 설치 close 구현을 SHA로 핀한 뒤 fast_shutdown=True와 기존 nonzero exit 보존 경로를 사용한다. watchdog·부모600초·ownedPID 회수·원 code와 policy code 구분을 유지한다. 빠른 종료에서 마지막 Python finally가 실행되지 않을 수 있으므로 COMPLETE_PRE_CLOSE는 기존과 같이 실제 child0+동일job/PID+완전한 artifact seal+provider/static/runtime 의미검증이 모두 충족될 때만 수용한다. native 실패를 exit0으로 바꾸지 않는다.

SDK watchdog은 close 전체에 선행하지 않고 `app.shutdown()` 직전에만 활성화된다. 그 이전의 Replicator·stage·stdio 정리 지연은 부모600초가 담당한다. nonzero fast 경로는 watchdog 활성화 전에 `os._exit(exit_code)`로 원 종료코드를 보존한다. 따라서 빠른 종료 설정만으로 모든 close 단계의 완료를 보장했다고 하지 않는다.

예상 소유는 sdk.py/validate.py/driver.py/test_host.py/config의 한정 관측·검증·핀·예약 규칙과 새 증거다. 원070 source/실행/실패 원장을 먼저 보존하고 새 계획의 비작성자 검토 후 구현한다. 설치·재부팅·실물·모터/CAN·학습·구매는 제외한다.

## 승인된 추가 실행과 원장 결속

070에서 원069 import **1/1을 이미 소비**했다. simulation은0/1이지만 정상 import 선행조건이 없어 실행하지 않았다. 이 제안은 자동 재시도를 하지 않는다.

사용자가 **import 추가1회와 새45분 검토·시간 예산**을 승인했다. 원069 원장을 새 namespace로 바꾸거나 삭제하지 않고, 실패 run/job/exit/terminal/remote-shell 원본을 `071/prior-import-failure.json`의 raw UTF-8+SHA로 봉인해 그 실패의 한정 후속1회라는 관계와 총횟수2를 명시한다. config는 이 proof의 정확한 ref/SHA·기존run/job을 핀한다. snapshot/예약 전에 원 job digest·목적·PID/parent chain·terminal FAILED/code1/최초world census 오류·exit timeout/actual1/policy124/REAPED·shell124를 서로 대조한다. None/bool/누락/다른 실패를 허용하지 않는다.

원격 원장의 기존 import행이 이 정확한 prior run/job/common signature와 맞고 총행수/목적횟수가 유효할 때만 import 두번째 예약을 추가한다. 빈/새 원장으로 후속을 시작하거나 세번째 import를 허용하지 않는다. simulation은 기존0/1을 유지하고, 새 정상 import 원본의 run/job/common signature와 예약을 연결한다. 실패도 예약 소비하고 중복run/job·추가purpose·위조predecessor는 거절한다. source/model/SDK 핀을 쓰는 실제 새 import가 수용된 뒤에만 simulation 슬롯1회를 사용한다. 이전 실패 import를 정상 증명으로 재사용하지 않는다. 추가 원장·proof 음성은 고정 이름/개수로 검사한다.

그 뒤 실제22초 개폐/6축/중력 시험과 RTX frame을 수용하고, MP4·full decode·출처JSON을 기존 Drive 날짜 폴더에 신규 저장·metadata 재조회한다. FAIL 영상은 FAIL로 명명하며 원래070의 실패나 미생성 영상을 덮지 않는다. 외부 hook 재시도 없음/동일 계열 비작성자 한계, 기존 provenance7/physical6 EXHAUSTED·eligibility2-next1과 새로운 보수적 world 분류 false-negative instance1을 구분해 보존한다.
