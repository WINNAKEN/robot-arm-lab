> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 075 실행 — 표현 교정 후 원 기준 재시험

사용자 지시: 정규화·게인 변환을 수정하고 포그 없이 재검증, 정지 통과 후 큰6축동작, 기준무완화/실물제외. 별도075시험으로074실패와원장무수정. 소유src/simulation/representation_trial/,outputs/isaac-representation-v1/. 새유한단위M45: 시작2026-10-29 23:00:10UTC,종료23:45:10UTC(한국10월30일08:00:10~08:45:10). 이는075작업의내부상한이며074사용자승인시간을연장했다고주장하지않는다. L2/L4각max2, native import1/smoke1/motion1 각600초/전체상한,600초미만남으면시작금지. 실패소비/단일lock/회수/실제종료코드유지.

074의13source복사본에만수정한다. Quaternion finite/unit범위거절을유지하고회전계수2를2/norm²로고친다. TCP와중력COM/축계산에동일하게적용하고원root1e−8m/중력/관절/바닥/정착기준불변이다.

뷰준비후첫양의dt전에tensorbackend로동일한명목Kp64/Kd16을설정한다. 실제tensor readback을원자료로기록하고값64/16 exact및engine0를선행조건으로검사한다. USD각도변환왕복을피하는방법이며gain튜닝/관측값반올림/허용오차확대가아니다. root는초기gain기록을첫행실제configuration과결속하고기존전행1e−6기준을유지한다. readback불일치시실패한다.

포그PointInstancer의visibility를invisible로설정하고실제USD getter로기록·root검사한다. 원모델/물성가정/고정seed자료/관절/프로그램52초/원cap/g−9.81/Kp64Kd16/0dt초기화어댑터/콜백관측/원그리퍼40mm/원SDK파일을유지한다. 반구형태추가없음,숨김은physicsAPI나충돌조건을바꾸지않는다.

HOST: 기존transport48/scene29/초기화14/수리15 및새정규화float32회전·COM/중력참조/정확gainreadback·잘못된각도변환·fog반대값음성을실행한다. 비작성자L4후실제SDK가져오기→2초정지전관측/표시/원기준수용→52초motion. 실패자료는원본으로유지하며파생packet을nativePASS로승격하지않는다. 통과시실제첫/중간/끝frame시각확인,ffmpeg10fps/프레임수/재생길이/full decode와Drive저장·metadata확인. 실물/보정/플래시/설치/재부팅/구매/학습없음,링보류유지.
