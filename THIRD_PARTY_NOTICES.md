# 외부 자료와 라이선스

프로젝트 자체 코드·문서에는 아직 별도의 재사용 라이선스를 선택하지 않았습니다. 저장소를 공개한 것과 전체 자료를 특정 오픈소스 라이선스로 허가하는 것은 구분합니다. GitHub의 [라이선스 안내](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)를 참고하세요.

## 참고 프로젝트

| 자료 | 사용 범위와 공개판 처리 |
|---|---|
| [Makerbase MKS-SERVO42D-57D](https://github.com/makerbase-motor/MKS-SERVO42D-57D) | CAN 프로토콜/전원/설정의 제조사 근거. 외부 패키지·매뉴얼 원본·제조사 펌웨어는 이 저장소에 재배포하지 않습니다. 자체 코덱/시험 구현은 `src/firmware`에 구분합니다. |
| [Waveshare ESP32-S3-RS485-CAN](https://docs.waveshare.com/ESP32-S3-RS485-CAN) | 보드 핀/인터페이스 참고. 제조사 SDK·데모 패키지는 포함하지 않습니다. |
| [Espressif ESP-IDF](https://github.com/espressif/esp-idf) | 외부 설치 의존성. 조회 브리지는5.5.6을 대상으로 하며 SDK 소스/도구는 포함하지 않습니다. 해당 프로젝트의 라이선스가 적용됩니다. |
| [Source-Robotics Faze4](https://github.com/Source-Robotics/Faze4-Robotic-arm) | 초기 링크 배치와 감속기 구조 참고. 수집 당시 실제 LICENSE는 **CERN-OHL-S-2.0**이며 README의 MIT 배지와 상충해 MIT로 단정하지 않습니다. 원본/변환 메시·외부 URDF는 제외하고 참고 기록과 기존 첨부 라이선스만 유지합니다. |
| [Thor](https://github.com/AngelLM/Thor) | 초기 외부 CAD 변환 실패를 조사한 참고 대상. 외부 CAD·변환 형상·패키지는 포함하지 않습니다. 과거 조사 스크립트가 있어도 원형 모델을 배포한 것은 아닙니다. |
| [SweepDynamics Armold](https://www.sweepdynamics.com/) | 초기 외관 방향 참고. 구매 CAD를 이 저장소에 포함하지 않습니다. |

자체 모델 설명에 포함한 `REFERENCE-LICENSE-CERN-OHL-S-2.0.txt`는 해당 참고 자료의 원문 보존용이며 프로젝트 전체를 그 라이선스로 재라이선스한다는 선언이 아닙니다. 과거 문서의 상표·제품명·제조사 사양과 링크는 각 권리자에게 속합니다.

새 외부 코드·모델을 도입할 때는 원출처, 정확한 라이선스, 수정 내용과 재배포 가능 범위를 먼저 확인하고 해당 고지/원문을 유지합니다.
