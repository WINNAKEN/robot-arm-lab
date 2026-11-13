# CAD/코어 각도와 BenchRun 단발 제어

`joint_angles.hpp`의 좌표는 고정 v2/025 리비전 기준이다.
CAD deg→core delta rad는 +1이며 core geometric rad = delta + pose rad다.
pose deg는 J1..6 순서로 `[15,-50,70,15,25,-10]`이다. CAD의0은 저장 표시 자세다.
이는 물리 모터/encoder의0이나 CAN direction0을 뜻하지 않는다.

절대좌표 변환은 `convert(joint, Coordinate)`로 세 좌표를 함께 반환한다.
`request_joint_step(request,joint,Step)`는 **상대 변위**만 받으며 offset을 더하지 않는다.
보정된 환산 결과가100pulse인 단발만 허용하고 기존 speed5/acc2·Gate/ticket/기한/정지/
CAN codec/관측 완료 경로를 통과한다. 임의 pulse나 절대 위치 목표를 보내는 API가 아니다.

기존2인자 BenchRun 생성자는 각도 보정 미승인이다. 새3인자 생성자는 축 순서와 일치하는
Calibration2개를 private const 배열로 복사한다. 신뢰된 설정측에서만 채우며 웹 입력에 노출하지 않는다.
각 보정은 measured/layout/boot/profile/axis/joint/fullsteps/microsteps16/reduction/dir0_joint_sign을
명시한다. 부품이 오기 전에는 measured=false를 유지한다. normal_approved=false 기본값도 유지한다.
감속비와 모터 부호를 CAD 관측 +1에서 추정하지 않는다. Profile::dir0_sign은 encoder count 부호다.

보정은 actor 수명 동안 교체할 수 없다. `revoke_joint_mapping()`은 되돌릴 수 없고 기존 정지 경로로
예약 이동을 폐기한다. 이미 전송/배달된 CAN 명령을 소급 취소하지 않는다. 유효한 Stop은 변환/보정
조건을 검사하기 전에 기존 경로로 전달한다. 기존 first fault/time을 보존한다.

보정 변경은 기존 actor의 정지 종결·단일 CanPort owner 해제 후 새 고유 boot/profile로
actor를 만들고 기존 부팅/유지보수/토크·제어권 절차를 다시 밟는다. 같은 identity로 다른 보정을
hot swap하는 것은 지원하지 않는다. 신뢰된 boot identity 유일성 전제는 기존과 같다.

이번 변경은 C++ 각도 제어 진입점이다. 기존 휴대폰 방향 버튼/HTTP schema는 그대로이며 숫자
각도 endpoint나 물리 교정을 자동으로 켜지 않는다. 링/충돌/강도/실물 한계·Isaac 승인은 포함하지 않는다.
구현 수용·검토 결과는 `.dev/joint-control-evidence/`를 따른다.
