# 오프라인 CI 설정 예시

`offline-checks.yml`은 공개 파일 검사와 조회 브리지 HOST 시험만 수행하는 GitHub Actions 템플릿입니다. 이 위치에서는 자동으로 실행되지 않습니다.

초기 공개 시 인증의 저장소 권한만 사용하기 위해 `.github/workflows/`에는 배치하지 않았습니다. 현재 Actions 실행 결과가 있다는 뜻이 아니며, 초판 게시 전 로컬 및 비작성자 HOST322검사가 통과했습니다.

후속에 적절한 인증 권한으로 CI를 활성화할 때 템플릿을 검토한 뒤 `.github/workflows/offline-checks.yml`로 옮기고 공개 manifest를 갱신합니다. 시험은 Python3.12와 C++17을 사용하며, USB·CAN·모터·원격 Isaac에 연결하지 않습니다. 인증 토큰을 파일에 넣지 않습니다.
