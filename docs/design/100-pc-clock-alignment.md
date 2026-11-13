> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 100 — 두 PC 시간 정렬 (승인 후 관리자 승인 취소로 미완료)

2026-11-01 상태 갱신: 사용자 `작업계속이어가'`로 OS한정100 범위 승인. 최초600초 안 두PC 읽기 완료, 로컬 UAC 요청1회가 Windows 사용자취소 오류로 종료해 service start/resync 각0. 원기한은 이후 만료·종결했으며 자동재시도/새anchor0, SDK/CAN0이다. 현재 결과는 [100-results.md](100-results.md)와 `outputs/pc-clock-alignment-100/result.json`을 따른다. 아래 본문은 승인 당시 제안 이력이며 당시의 “아직 미승인/미실행” 문구를 현 상태로 재사용하지 않는다. 승인 원문 바이트는 `outputs/pc-clock-alignment-100/before/approved-plan.md`에 있다.

---
# 100 — 두 PC 시간 정렬 제안 (아직 미승인·미실행)

099의 실제 원격 측정에서 시작 준비9.890초는 표본 구간에서 분리됐고, 표본왕복은wall14.688ms/mono16ms였다. 그러나 remote-local offset 가능 구간은 **+3.410628~+3.429315초**로 원±1초를 벗어났다. 이는 현재 두PC의상대시계차이를확인한것이며 어느PC가올바른UTC인지까지확정하지않는다. 원격Kit0/sitefalse·양EOF/cleanup확인·원로그보존 후 SDK/SimulationApp 전에 중단했다.

로컬읽기조회는 W32Time **Stopped/Manual**, Type=NTP, NtpClientEnabled=1, NtpServer=`time.windows.com,0x9`, SpecialPollInterval=16384를확인했다. w32tm status는서비스미실행0x80070426이었다. 서비스중지만으로실제UTC오류의유일원인을단정하지않는다. 원격서비스상태는099실패후추가SSH금지를지켜미조회다.

현재099승인은동결실행기의단일2700초만허용했고시각/서비스설정변경은포함하지않았다. **다음사용자승인을받기전서비스시작·resync·추가SSH는실행하지않는다.** 이번파일은구체작업제안이며코드검토완료나실제시간정렬주장이아니다.

## 제안하는 한정 OS 작업

최대10분의시간정렬단계다. 시작시같은PC의monotonic+600초로기한을1회고정한다. wall시각은이번수정대상이므로기한소비에쓰지않고전후관측에만기록한다. 각명령/대기는같은단조잔여시간으로제한하며기한후새명령0·재부팅/부분실패의자동anchor재시작0이다. 늦은OS반환은UNKNOWN/실패로남긴다. 실제CAN/SDK/SimulationApp/native물리0이며099예산/marker/원실패를삭제·reset하지않는다.

1. 로컬과기존SSH별칭isaacpc에서 W32Time 상태·기존time provider/peer·동기화상태만읽어원본출력을보존한다. 명령은 `Get-Service W32Time`, `w32tm /query /status /verbose`, `w32tm /query /configuration`이다. 명령실패/접근거절은실측실패로남기며권한/보안정책을수정하지않는다.
2. 승인된대상에서서비스가Stopped일때만 `Start-Service W32Time`을실행한다. 이미Running이면다시시작하지않는다. StartupType·NTP서버·레지스트리·도메인정책·timezone은바꾸지않는다. 시작한서비스를임의Stop/Restart하지않고기존정책을따르며작업후실제상태를기록한다.
3. 각PC의기존time provider를그대로사용해 `w32tm /resync`를각1회요청하고returncode/raw를보존한다. `Set-Date`, 외부서버강제지정, `/config` 변경, 설치·재부팅은범위밖이다. 관리자권한/시각데이터/peer접근에실패하면추가resync/우회설정없이중단한다.
4. 이후status/verbose를다시읽어실제최근동기화·Source/Leap/Stratum/offset관측을기록한다. resync명령종료0만으로정렬성공을선언하지않는다. 값이오래되거나시간출처/동기화가불명확하면SDK를시작하지않는다. 필요한대기/읽기재관측도처음고정10분안이며새기한을만들지않는다.

이OS작업은PC의벽시각과서비스상태를변경하므로기존099단일시뮬승인과별도확인이필요하다. 승인질문은이작업의영향과명령을대상으로한다. 실물CAN/급전/flash/모터·게인/cap·물리기준/모델수정으로해석하지않는다.

## 시뮬레이션 재개 경계

099 runtime-budget은실패로소비·종결됐고재사용하지않는다. 시계가정렬돼도old099를재발사하거나수동으로anchor/marker를고치지않는다. 이후새실행namespace/비활성metadata결속을준비·필요한비작성자검토를완료하고새2700초의사용자명시승인을받는다. 이미포괄승인을받은경우중복질문하지않는다.

시간변경이끝난뒤새monotonic/UTCanchor를잡고첫시뮬원격명령부터45분을시작한다. 원±1초clockguard/.25초coherence·headroom·watchdog·목적각1을유지한다. import→정지수용→42초진단이며실패/지연은다음NOT_RUN,실물CAN0이다. 시간정렬명령/추정값으로실제ready-clock인증을대체하거나기준을완화하지않는다.
