> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 057 — 실제 module에 결속한 Torch metadata

사용자 2026-10-29 「이어서 진행해 메타데이터 맞춰봐」에 따라056 실패를 수정한다. 새 계약은 ambient distribution 탐색과 실제 module에 대응하는 고정 distribution을 분리한다.056 source/원장3예약과 기존 계보는 동결한다. 실물/재부팅/설치/전역설정/모터/CAN/학습/링 작업은 제외한다.

M9/45분(15:03~15:48UTC), 소유 src/simulation/metadata_session7파일, 계획057, outputs/isaac-metadata-v1 근거. L2/L4각max2 비작성자 읽기전용 검토, 이전 외부계열 hook차단 재시도없음/same-family fallback 잔여 명시. 이전 provenance7/physical6EXHAUSTED·eligibility2-next독립실측작성자수용1 충분 임계 유지, class/착지/예산종결 판정을 요구한다.

Torch/Torchvision만 module-bound metadata를 새로 소유한다. 실제 module 파일의 parent package root에서 고정된 dist-info의 METADATA/RECORD를 직접 읽는다. 전역 importlib.metadata 검색 결과는 ambient 필드로 원문 보존하며 수용 근거로 사용하지 않는다.048 full seal에 있는 METADATA/RECORD/module-init의 경로와 SHA를 새 source에 고정하고 producer가 실제 바이트·METADATA Name/Version·RECORD의 해당 module파일 소유 항목 및 해시와 실제 module파일 해시를 대조한다. root도 관측된 증거 경로/해시를 같은 고정 의도표와 실제 module origin/distribution_root에 결속한다. 다른root/module/version/누락/변조/소유불일치/ambiguous는 실패다. bound 조회 실패를 ambient fallback으로 통과시키지 않는다. 고정 producer/PID/hash 관측을 신뢰하며 임의로 완전 위조된 모든JSON의 OS attestation을 주장하지 않는다. 나머지6provider/SDKnumeric/typednamespace/GPU13/전후5ID/CAD4facet 계약은 보존한다.

새 원장은056 원장 바이트 SHA와 nested history를 보존한다. 새 사용자 지시·metadata 권위의 source에서 audit900s/diag300s/connection600s 각1회 순서·원본 proof·동일signature·freshness300s·실제exit/PID/hash/transport를 유지한다. source 변경은 이전 성공 proof 재사용 권한이 아니다. 실패 후 동일목적 재실행/수리출하없음. source는056의 경계 코드를 내용으로만 복제하며 이전 public/entry는 호출하지 않는다.

호스트 기존11시험 보존, 실제056 mismatch 자료 원본보존, temporary distribution의 ambient cu128/실제 cu130 정상·METADATA/RECORD/module변조·소유누락 및 root consumer의 resealed 증거변조 거절을 검증한다. 추가값은 HOST MODEL 명시. AST/범위whitespace/최종독립L4 뒤 실제3목적 실행. 설치변경없이 실제 module/metadata 출처를 확인한다. 로봇 연결 성공과 진단 성공은 분리한다. 기존 실패/질량관성가정/047미해결은 소급변경하지 않는다.

단계 명확화: baseline 진단의 SDK cu128 module은 bound 조회가 고정 cu130 의도표에 맞지 않으면 명시적 ERROR/원인/빈 proof로 기록하고 진단 관측 완료는 허용한다. 이 상태는 PREAPP 후보의 근거일 뿐 최종 접속 허가가 아니다. bound VERIFIED 주장에는 고정 proof 전체가 필수이며 잘못된 proof/상태누락은 진단에서도 실패한다. 실제 연결 require_observation은 VERIFIED와 module-bound pins/root/version을 필수로 요구한다. ambient fallback은 어느 단계에서도 bound 성공으로 표시하지 않는다.

## 실제 Windows RECORD 보완 — 호스트/파일 한정 후속

실제 연결에서 Torch bound VERIFIED, TV RECORD는 canonical init경로에 unhashed `/`행과 hashed `\`행이 함께 있었다. 사용자 metadata수정 요청 안에서 남은L2/L4 R2로이표현계약을보완한다. 원R1source/실제3예약/실패는보존동결하고 추가SDK/App실행은하지않는다. 후속은호스트수리·실제3파일읽기전용대조만,45분캡유지다. RECORD상대경로를slash정규화하되절대/drive/순회는거절한다. canonical소유항목들중해시와크기가둘다있는항목최소1개가실제init에일치해야하고, 같은canonical항목의모든nonemptyhash/size는같아야한다. 해시없는행은소유증거로사용하지않으며둘다빈경우에만중복참고로허용한다. 충돌·부분빈hash/size·소유증거0은실패다. METADATA/RECORD/init 전체SHA핀과root소유정책은유지한다. 실제metadata파일을읽어같은helper로검증하되SDK모듈import/앱/로봇/새연결은금지한다. 이파일검증성공은전체연결성공이아니다.

RECORD경로정책의범위: 소유증거후보는 slash만정규화한 package/__init__.py의root상대행이다. ..를해소하거나절대경로를상대경로로변환해후보로채택하지않는다. Torch RECORD의../../bin/torchrun.exe 같은다른설치파일행은이번init소유검사의범위밖이며후보가아니다. 전체RECORD바이트해시핀은그대로검증하므로그행을임의로고치는수리는없다.
