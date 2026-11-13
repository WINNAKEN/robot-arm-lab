> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 145 — ESP 배포 실행기 RAM helper 중복 호출 수리

사용자 최신 승인인 모터OFF·조립유지 ESP조회전용펌웨어준비/업로드를 완료하기 위한 새 실물 통합 결함 수리다.144의검토 L2/L4는4회로동결하고F2제품/32핀/실패로그를 보존한다.144실제배포는 write/restore 둘다 esptool.main이 이미stub인외부esp에 다시run_stub을호출해flash작업전mem_begin overlap으로실패했다.145는그SDK adapter결함만다루며기존제품 요구/허용목록/원격권한/모터전원은넓히지않는다.사용자의업로드지시는성공할때까지필요한수리를포함하므로작업범위재승인을묻지않는다.

S/제품3파일(본계획·새deploy145.py·adapter HOST검증),Root와비작성자새1500초/마감180초. 단순 SDK인자adapter수리로L2생략·비작성자L4최대2회,기존144 reviewer4회예산은재개하지않는다.새코드는144 deploy144.py를새출력폴더에그대로복사한후ROOT는동일,OUT는144의검증자산,worker는145자기파일을호출하도록유지한다. 수정은이미검증한동일장치와run_stub한외부esp를공식esptool.main에전달할때 --no-stub 인자를추가해중복주입을막는것이다. run_stub는connection당정확히1회이며동일연결MAC/security/flashID검증은보존한다. 기존14432핀과허용app0/otadata영역·전체flash검증·readback·USB6초안정성·복구는동일하다.145자체소스해시와비작성자PASS의별도게이트를추가한다.

HOST는설치된esptool실제main을fake외부stub에연결해기존인자는run_stub2회실패,수정인자는호출0회추가로operation도달함을재현한다. 최종수리검토후같은후보를배포하며실행기는검증자산과동일한144폴더의공유runtime경로에기록한다.144최초실패로그는145/attempt144에원바이트스냅샷보존했으며,145종결시새실행로그·결과를145에도복사하고실행argv가145worker를가리킴을명시한다.새SDK쓰기는1회,실패시기존동일장치바이트복구1회·readback을수행한다.실제CAN조회·모터급전·회전0유지.미완료를PASS로선언하지않는다.
