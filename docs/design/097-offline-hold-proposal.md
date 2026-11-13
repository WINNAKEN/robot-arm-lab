> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 097 — 고정 목표 정착 진단의 오프라인 준비

2026-11-01 KST. 사용자 「좋아 다음 작업이어가」에 따라 096의 다음 단계인 정착 진단을 구체화한다. 이번에 허용된 작업은 저장 자료 읽기, 별도 프로그램 후보 생성과 HOST 검증, 비작성자 검토, 로컬 기록이다. 새 원격 45분 예산은 승인되지 않았다. native/SimulationApp/SDK/SSH/네트워크/실물 CAN/serial/급전/모터/flash/보정/설치/학습/외부 업로드는 실행하지 않는다. hardware_approved=false를 유지한다.

## 문제와 선택

096은 원095의 33~34초 동일 목표 구간에서 J3/J5가 목표를 지나고 오차가 증가함을 확인했다. 단순 지연이나 유일 원인은 확정하지 않았다. 기존 기록의 34초 뒤에는 다른 축의 목표가 바뀌므로 같은 정착 관측을 연장할 수 없다. 게인·cap 변경보다 먼저 전체 목표 벡터를 유지한 관측이 필요하다.

이번 후보는 원095 프로그램의 첫 9개 segment(0~34초)를 그대로 유지하고, 이후 원래 경로 대신 8초의 고정 목표 hold 하나를 붙인다. 총42초, 120Hz 5040step/5041관측, stride12·10fps 421capture다. 33~42초가 같은 여섯 팔 축 및 세 그리퍼 자유도의 목표이고, 명령속도는0이다. 원34초 checkpoint를 삭제하거나 늦추지 않는다. 후보의 끝42초에도 동일 기준의 checkpoint를 추가한다. 원52초 전체 경로를 완주한 것으로 표시하지 않는다.

## 소유·보호·검토

소유는 이 계획, docs/design/097-results.md, outputs/isaac-hold-proposal-097/와 최소 HANDOFF prepend/SESSION_HANDOFF append다. 원src 전체·CAD/URDF/BOM/펌웨어·095/096 원본·과거 실패/소진/임계는 수정하지 않는다. 원096 보호4482경로에 현재096 소스/증거/검토/ignored ZIP까지 더한 SHA256 목록을 만들고 전후 확인한다. 기존 공유 인계의 바이트는 그대로 보존한다.

검토 단위097은 L2최대2/L4최대2, 동일계열 비작성자 한 명 재사용, 단일 검토 투입은 검수급45분 상한이다. 기존 Sonnet bridge의 lint 차단과 동일계열 폴백에 대한 사용자 선택은 유지하며 새 bridge 시도/수리/설치 없이 진행한다. 공통편향을 잔여 리스크로 기록하고 외부계열 가용 시 전제 재검증을 우선한다. 지적 합집합·class·착지·폐쇄·소진 및 다음 임계를 각 라운드에서 요구한다. 예산 소진 후 자동R3/수리/새native는 없다.

## 오프라인 제작·검증

기존095와096 program.json 바이트가 같은지, 096 검토의 소스18 핀이 현재 바이트와 같은지 먼저 확인한다. stdlib-only verify.py는 원 프로그램을 strict JSON으로 읽어 첫9개 segment와 나머지 설정을 복사하고, 같은 목표의 hold8초 및 파생 duration/step/capture 숫자만 바꾼 별도 program.json을 생성한다. 원scene.py의 실제 target_at/validate_program/checkpoint를 로컬에서 SDK 없이 호출한다. 모델은 기존 URDF를 기존 순수 Python validate.py.pmodel로 읽으며 SDK/물리 모듈을 호출하지 않는다. reference.py는 토크 reference 모듈이며 URDF reader로 호출하지 않는다. 소비 경로를 실측한 뒤 불가능하면 미실행으로 남기고 대체 관측을 물리 성공으로 세지 않는다.

0~34초 4081개 표본의 targets/reference_velocity/velocity_targets/gravity/opening/phase를 원본과 비교한다. 33~42초1081표본의 전체9목표와0속도를 확인한다. program의 기타 키·게인64/16·settling·카메라·바닥·중력·40mm opening 및 원 물성/한계는 유지한다. 원endpoint 2/8/15/25/34초를 보존하고42초만 추가되는지 실제checkpoint 경로로 확인한다. 합성의 q=target/qd=0 양성과 J3/J5 원 실패 수치 음성을 함께 주어 34초 실패를42초 성공으로 덮지 못함을 확인한다. 합성 결과를 native 측정으로 표시하지 않는다.

원checkpoint삭제, prefix축목표변경, hold중다른축목표변경, gain/settling완화, 수량변조의 음성을 실제 검증 함수에 통과시켜 모두 거절되는지 검사한다. 원프로그램을 원위치에 덮지 않으며 검토 freeze 이후 후보/하네스/증거를 변경하면 새라운드로 보존한다. 쓰기 전후 보호해시·Python compile·HOST를 먼저 통과하고 L4는 후보 프로그램과 소비 경로까지 검토한다.

## 후속 원격 시험의 구체 제안 — 이번에는 미실행

후속098은 이 후보를 새 source/run namespace에 결속하고 096의 수정된 recovery.py 및 driver caller를 통합하는 별도 구현 단위다. 현재096 소스의 native 차단을 해제하거나 deadline/native quota를 고치지 않는다. 097의 후보검토 PASS는098의 실행기/활성화 검토 PASS가 아니다. 사용자 승인 후098 L2최대2/L4최대2의 새 유한 검토에서 통합·HOST를 마친다. 검토 소스/후보/모델/수용 기준과 실행 바이트를 freeze로 결속한 뒤에만 단일 활성화를 허용한다.

제안 예산은 수리·검토를 제외하고 **첫 원격 명령 직전부터 새45분(2700초)**이다. 원095/096 시계·원장·검토 상태를 재사용하거나 초기화하지 않는다. 새 clock/activation은exclusive 예약하며 실패도 소비한다. 새 목적별 native는 import1 → 정지1 → 고정목표진단motion1, 실패도1회소비, 추가SDK/자동retry0이다. fresh import와2초 정지 수용이 선행되어야motion을 발사한다. 정지실패/핀불일치/기한초과면 중단하고 남은 증거만 회수한다.

native watchdog은 import/정지600초, motion900초. 기존 transport는 watchdog+150초(750/1050초)로 기다리므로 이 wrapper 여유도 포함한다. 회수는 각export/SCP최대300초, 한 번 예약한 **전체600초**를공유하며 절대종료기한과min으로 제한한다. 각단계는 **transport750/1050+회수600+정리30**을 전부 남겨야 새 발사가 가능하다. 따라서 import/정지 최소여유1380초, motion1680초, 등호도거절. 시계종료는 start+2700, import/정지발사마감 start+1320, motion발사마감 start+1020이다. 세목적최악시간합은 native2100+wrapper450+회수1800+정리90=4440초로45분을넘는다. 정상종료가빨라야세목적이들어가며완주보장은없다. 늦으면motion미실행, 예산자동연장없음.

위여유검사는 coordinator/driver의최초진입뿐아니라원격폴더생성·upload·압축해제·SDK/lockprobe를마친뒤supervisor송신직전과원격supervisor의실제childspawn직전에도수행한다. 후자는원job/config의절대deadline과같은purpose별1380/1680을읽고현재원격시각으로검사하며,검사실패는spawn0으로기록한다. 검사/원장예약/childspawn사이의시간도childspawn직전재검사한다. 원격시계와로컬시계의차이는이번시계의선행읽기로기록하고기한은보수적으로적용하며불확실하면발사거절한다. upload/생성/확장/probe도각timeout을남은절대시간으로제한한다. 전송·probe가여유를소비한경계에서반드시발사를거절하는실제caller와supervisor의HOST음성이098통합검토의필수조건이다. 이번097은이runner코드를구현하거나native준비완료로표시하지않는다.

첫 원격 export로 수정 회수경로를 실제 검증한다. 닫힌원자료의 exclusive archive/receipt·hash/CRC·parent PID/result/seal을 검증하고 기존consumer는별도실행한다. 회수실패는 native미실행/물리성공으로바꾸지않고 최초validation/native transport/회수실패를모두보존한다. 회수실패뒤자동우회·재복사·재시도도하지않는다. 기존095 실패원본은계속보호한다. 네트워크/SDK설치·보안·서비스·전원정책변경은없다.

판정은 원checkpoint의위치≤0.5° 및속도≤1°/s와나머지9자유도기준을유지한다. 34초실패후42초통과라도전체motion은원consumer의실패를유지하며별도관측결과로만「고정목표연장중기준진입」을보고한다. 34~42초의부호오차·속도·최초진입/이탈·같은목표의연속표본범위·마지막1초의오차/속도범위를기록한다. 표본기준전축동시통과와J3/J5개별통과를분리하고유한관측창밖의정착/유일원인은확정하지않는다. 42초까지미달이어도지속편향/발산의유일원인확정이아니다. 첫구간의명령은같지만실제동역학재현은확인대상이며원095의실측을새run증거로대체하지않는다.

521PNG가아닌421PNG/42초진단의원봉인·연속journal·frame clock/PNG CRC·종료상태와전체decode를대조한다. 영상/원표본은진단범위만표시한다. 실제PD토크/포화UNKNOWN·moving-root독립교정NOT_DONE·물성가정·링보류·포그숨김·자기충돌OFF/바닥ON·정착15·velocity-onlyEXHAUSTED는유지한다. CAN/급전/flash/모터/보정은계속금지한다.

## 9개 이진 수용 기준

AC1 권한: 로컬오프라인만,원격/SDK/native/실물0·hardwarefalse. AC2 보호: 원095/096·과거보호·소스/모델/물성/기준·인계원문바이트보존. AC3 후보: 정확첫9segment+같은목표8초,42초/5040/5041/421. AC4 경로: 실제기존target_at/validate_program/checkpoint로prefix4081/hold1081·9DOF검증. AC5 판정: 34초원실패/원기준보존,합성/물리·endpoint/관측구간분리. AC6 음성: prefix/hold/게인/기준/수량/checkpoint변조거절·정상양성통과. AC7 후속예산: 2700/600/900/300/600/150/30·1380/1680·실제spawn직전검사·목적별1회/새freeze·무재시도/미구현표시. AC8 검토: A/B선행·비작성자9항·합집합/class/소진/공통편향·유한예산. AC9 인계: 실제실행여부/한계/후속승인대기·정확소유localcommit/push0.

097 완료는 검토된 오프라인 후보와 구체 제안의 보존이다. 098 구현/통합/활성화·새45분·수리원격성능·물리정착은 NOT_RUN/PENDING_USER_SCOPE_AND_BUDGET다.
