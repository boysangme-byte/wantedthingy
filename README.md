# Wanted Auto Mailer (Local)

원티드 최신 채용공고를 조건에 맞춰 모아서 메일로 보내는 로컬 자동화 스크립트입니다.

## 1) 설치

```bash
pip install -r requirements.txt
```

## 2) 설정
- `config.json` 에서 필터를 수정하세요.
  - `locations`: 포함될 지역 문자열 목록 (예: ["서울", "경기"]) 
  - `jobs`: 직무 키워드 목록 (예: ["개발", "데이터", "AI"])
  - `years`: 최소 경력(년)
  - `email`: 수신자 이메일 주소

- 발신자 Gmail 계정 환경변수 설정 (PowerShell):
```powershell
$env:MY_EMAIL="your_gmail@example.com"
$env:MY_PASSWORD="your_gmail_app_password"  # Gmail 앱 비밀번호 권장
```

## 3) 실행
```bash
python wanted_mailer_auto.py
```

성공 시 `last_id.txt`에 마지막 발송 공고 id가 저장되고, 다음 실행부터는 신규 공고만 전송됩니다.

## 3-1) 웹 UI 실행(선택)
```bash
pip install -r requirements.txt
python app.py
```
브라우저에서 `http://localhost:5000` 접속 → 설정 저장, 미리보기, 바로 보내기 버튼 사용.

## 4) Windows 작업 스케줄러 등록
1. 작업 스케줄러 열기 → 작업 만들기
2. 일반: 사용자 로그온 여부와 관계없이 실행, 최고 권한 실행 체크 권장
3. 트리거: 매일 오전 8시 등 원하는 시간으로 설정
4. 동작: 
   - 프로그램/스크립트: `python`
   - 인수 추가: `wanted_mailer_auto.py`
   - 시작 위치: 이 프로젝트 폴더 경로
5. 조건/설정: 실패 시 재시도, 일정 시간 초과 시 중지 등 필요시 구성

## 5) 문제 해결
- 메일 전송 실패: Gmail 앱 비밀번호 사용 여부 확인, 환경변수 재설정
- 요청 실패: 잠시 후 자동 재시도 되며, 네트워크/방화벽 확인
- 공고 누락: `config.json`의 키워드를 영문 포함으로 확장하거나, `years` 값을 조정하세요.
