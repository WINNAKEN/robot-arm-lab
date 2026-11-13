> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 087 — CAN 읽기 전용 진단 준비 결과

2026-10-30. 사용자 구현 요청에 따라 086 체크리스트의 다음 단계인 읽기 전용 실행부를 만들었다. 현재 펌웨어의 정상 운전/유지보수 경로를 재사용하지 않고 독립 Runner와 비활성 ESP32-S3 프로젝트로 분리했다.

## 구현과 모듈 없는 검증

- 선택ID1/2 하나에 enable(3A)→운전상태(F1)→원시위치(31)→속도(32)를 각1회 조회한다. 실제 송신 프레임을 ID/표준DATA/DLC/opcode/checksum까지 확인한다. 설정쓰기·F3/F7·이동·홈·보정·heartbeat·자동retry/restart는 없다.
- 기본 생성/미승인프로필은무I/O, 실제 main의승인은false와static_assert로고정한다. 명령 첫바이트를검사하므로F1 F3의정상checksum을F3명령으로혼동하지않는다.
- TX접수/실제완료/RX를구분하고시간·오류·추가응답·저널·최종close를확인한다. 후보시간조건은087의새HOST진단조건이며기존정지시간/허용기준을바꾸지않는다. 실제선로도착시각/응답원인성은입증하지않는다.
- 작성자 및 비작성자 HOST 각각 **72시나리오·849단언 PASS**, 쓰기 opcode/승인확인생략/10ms완화 변형 **3종 검출**. 실제 main+SDK선언stub 독립링크/실행은하드웨어호출0과설정승인값무시를확인했다.
- L2R1·L4R1 PASS9/0. 이후087B L2R2에서이미설치된SDK의독립타깃빌드만검토했다. 동일계열폴백편향은남는다.

## 실제 ESP32 타깃 빌드

기존 ESP-IDF5.5.6 commit880a203ae603d08a94d06aa01e0d6761958e5e9e/기존컴파일러로 독립프로젝트를1회 build했다. 실제 exit0·timeoutfalse·**warnings0**, ELF3,151,200bytes/BIN163,008bytes가 생성됐다. compile_commands에서새main/진단/codec/TWAI경로를확인했고, 기존app_main은이빌드에없다. 원소스/기존입력해시는전후동일하다. 최종 비작성자 L4R2 **PASS9/0**에서 실제7산출물 해시·타깃 경로·빌드 경계를 재확인했다. target-build/result.json과L4-r2.json을참조한다. 빌드 timeout/강제종료 실패 경로의 별도 fault injection은 NOT_RUN이다.

087A 사용문서/동결의‘actualtargetSDK NOT_RUN’은B검증전의기록이다. 현재빌드는여전히 **비활성 타깃**이다. 실제보드에부팅/플래시하지않았고CAN통신도하지않았다. 생성된sdkconfig는FREERTOS_HZ=100으로, 활성loop의1ms시간성능은미검증이다. 후속실물프로필/RTOS검토전까지승인false를유지한다.

## 수령품과 남은 항목

주문 화면은Waveshare ESP32-S3-RS485-CAN-U로확인했다. 도착 모터사진의몸체라벨SERVO42D_485는보존하되부착드라이브의통신규격을그라벨만으로확정하지않았다. 드라이브CAN옵션/HW/FW·실제ID/bitrate·단자·전원시자동동작은실물대조대상이다. 하드웨어정보를추측해프로필승인을true로만들지않았다.

다음은수령품식별→무전원배선/종단→보드단독확인→실물정보에맞는읽기진단활성조건검토다. 모듈이왔다는이유로이준비BIN을플래시하거나자동급전/조회하지않는다. 실물보정·모터운전·급전·통신·플래시·구매·재부팅·Isaac재접속은계속NOT_RUN이다. 최종6축/그리퍼지원확장이나실제정지/토크검증도아니다.

사용법: [087A 진단 사용문서](../specs/can-readonly-diagnostic.md). 수령 절차: [기존 체크리스트](../specs/can-arrival-readonly-checklist.md). 증거 정본: `.dev/can-readonly-evidence/README.md`와검토·result파일.
