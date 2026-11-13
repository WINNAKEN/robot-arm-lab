> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 070 — 오류 publication과 SDK 정리 분리, 최신 모델 실제 실행

2026-10-29 사용자 명시 승인: “새 검토 예산으로 오류 기록 실패해도 앱 종료가 되도록 수정하고, 최신 모델 Isaac 시뮬레이션이랑 영상 구글드라이브 저장까지 계속 진행”. 실물 보정·모터/CAN·플래시·설치·재부팅·구매·학습 제외. 가정 질량/관성, 링 보류, proxy selfcollision OFF 유지.

069A L4 R2 BLOCK8/1 및 LG069A-R1-4의 남은 stderr/publication 예외를 고정 입력으로 삼는다. 기존 원본·재현·provenance7/physical6 EXHAUSTED·eligibility2-next1·047/063/066 이력을 유지한다. 사용자 승인에 따른 구조 변경이며 이름만 바꾸어 원 검토/실행 횟수를 초기화하지 않는다. 실제 SDK의 069 import/simulate_capture는 지금까지 각각0회다.

## 유한 단위와 소유

전체 실행 상한은 **13:50:12–14:35:12 UTC,45분**. A는 sdk.py/driver.py/test_host.py의 3파일 한정 수리 S단위(25분,14:15:12까지), B는 승인된 기존 전체11파일 경로를 읽는 실제실행·영상/보관 M검수급(전체 상한 안에서 완료). A/B는 코드 작성과 실제수용을 구분하며 native는 A L4 PASS 후에만 시작한다. 공통 L2최대2, A L4최대2. 외부 hook의 기존 거절은 재시도/우회하지 않고 기존과 같은 비작성자 같은계열 fallback 한계를 기록한다.

수정 소유: `src/simulation/latest_scene/sdk.py`, `driver.py`, `test_host.py`; 이 계획; 신규 `outputs/isaac-gripper-v1/070/` 증거·출처·영상 및 최소 인계. 모델16파일, B의 scene/capture/program/test_scene/README, config/validate, 기존CAD/BOM/firmware/core/.dev 원자료는 수정하지 않는다. sdk/test_host는 별도 작성자, driver/통합/실행은 root, 비작성자가 L2/L4를 수행한다. 같은 저장소의 다른 작업을 되돌리지 않는다. 실행에 필요한 입력은 새 job으로 봉인하며 미실행069 준비 bundle을 재사용하지 않는다.

## A 구조와 수용

first-fault 수집은 메모리만 변경하며 stderr/파일 I/O를 하지 않는다. publication은 별도 함수로 분리하여 write/flush/format/serialization 오류도 잡고 primary를 바꾸지 않는 secondary로 저장한다. publication 도중의 오류에 다시 같은 출력 함수를 재귀 호출하지 않는다. 출력 전부 실패 시 내구적 저장을 보장하지 않으며 nonzero와 메모리 primary/secondary·정리 시도 여부만 구분한다.

SDK app.close는 가장 바깥 독립 finally에서 생성된 app에 정확히 한 번 시도한다. 초기 app이 반환되기 전에 ctx.app만 생성된 startup 실패도 포함한다. 초기/status/collector/postcheck/artifact-seal/publication/close 중 어느 오류도 정리 경로 진입을 막지 못해야 한다. app이 생성되지 않았으면 close0회. close 자체가 실패하면 시도1회·code1이며 종료 성공으로 표현하지 않는다. close가 정상 반환하거나 의도된 SystemExit(code)인 경우 실제 요청 code와 대조한다. 첫 오류가 있으면 close SystemExit(0)가 이를 성공으로 덮지 못한다. COMPLETE_PRE_CLOSE 원자료는 실제 종료0+부모/자식 PID·봉인·동일 job을 모두 확인하는 기존 consumer 조건에서만 수용한다.

driver native 외곽도 예외가 생겼을 때 ctx.first_fault를 primary로 전달하고 outer publication 오류는 별도 secondary로 기록한다. 그 기록이 실패해도 원 code1을 유지하고 어떤 출력 실패도 native 성공을 만들지 않는다. 기존 directPID/reaped/원 actualexit vs policyexit/단발 예약/timeout600/source snapshot/import-proof/provider/canonical 전체검증은 그대로다. plan SHA만 이번 승인 계획으로 바꾸며 remote069 슬롯은 유지한다.

호스트 대조의 기대 이름/개수를 고정한다. 적어도 정상, collector 실패, terminal 단독 실패, stderr 단독 실패, terminal+stderr 동시, close 단독, collector+terminal+stderr+close, 초기 status 실패(app없음), app부분생성 startup실패, postcheck실패, close SystemExit0가 원실패를 덮지않음, close nonzero, 실제 producer/외곽 publication다중실패를 포함한다. 실패는 OSError뿐 아니라 BaseException 경계도 검증한다. 원069R2와 수정본에 같은 실패 주입을 사용하고 primary/secondary/close실제횟수/return 또는 실제 child exit코드를 각각 확인한다. 기존 host24/semantic28/B36 근거를 보존하며 변경 호출부의 적절한 회귀만 재실행한다. host 대역은 실제 SDK 성공으로 승격하지 않는다.

## B 실제 실행과 영상 수용

L4 PASS·source freeze 이후 068 승인 제출자료의 모델16 SHA/bytes/canonicalXML, B5 SHA, SDK/source/provider 핀을 다시 확인하고 원격 기존 환경만 사용한다. native `import` 최대1회/600초, 수용 시 같은 공통입력으로 `simulate_capture` 최대1회/600초. 실패도 원래069 원장에 예약 소비하며 소스 수정 뒤 자동 재시도/다른 namespace/슬롯 증설은 없다. 각 native 전에 원격 Kit가0임을 확인하고 다른 세션 프로세스에 손대지 않는다. 숨김 실행·keepawake·ownedPID 회수 조건을 유지한다.

동작은 069의 승인된 고정22초/120Hz2640step/15fps331frame 프로그램 그대로다. logical gripper 0..94mm에서 두 슬라이더+피니언이동을 관측하고 6축±3도 왕복, 마지막3초 중력ON, 원 cap 및 nativeFF/실제 관성·FK·clock·phase끝 정착을 원자료에서 대조한다. 추종실패는 유효 동역학FAIL로 표시하고 목표치/게인을 바꾸거나 state를 재설정하지 않는다. 실패가 artifact/SDK/렌더 문제이면 그 경계FAILED로 보존한다. 링/물리기어 힘/쥠힘/충돌없는 전체경로/실물 정확도 수용을 주장하지 않는다.

실제 RTX PNG만 사용한다. renderer scheduled rationaltime/세 node compute_count/동일RP ReferenceTime·실제 physics state 불변·shape/CRC/SHA/blank/scene변화를 검사하고 첫/중간/끝 이미지를 열어본다. native frame을 못 얻으면 software replay로 대체하지 않는다. 유효 FAIL 시험이라도 실제 영상이 있으면 FAIL로 명명해 저장할 수 있다.

기존 ffmpeg로 MP4를 만들고 ffprobe fps/frame수/길이와 full decode를 확인한다. 현재 `docs/GOOGLE_DRIVE_ARCHIVE.json`의 날짜별 폴더를 재조회하여 신규 파일명으로 영상+출처JSON을 업로드한다. metadata 이름/크기/MIME/부모를 재조회하며 remote SHA가 노출되지 않으면 로컬SHA 확인과 구분한다. 기존영상/권한/공유설정은 수정하지 않는다. 업로드 미완료를 완료로 표시하지 않는다.

마지막에 실제 사용 슬롯/SDK·물리·렌더/host·review/Drive 상태를 구분한 manifest·인계와 소유범위 local commit을 남긴다. 실패 원자료·최초오류·닫힌3지적과 열린 경계를 보존한다. 예산·검토·실행 슬롯을 넘겨 재시도하지 않는다.
