# LOG Kios — 연구실 출입자 등록 키오스크

연구실 방문자 출입 기록을 위한 Flask 기반 키오스크 웹 애플리케이션입니다.

## 📋 주요 기능

- **단계별 등록 플로우**: 소속 → 부서/연구실 → 인원 → 정보 입력
- **직접 입력 지원**: 사전 등록 목록 외 자유 입력 가능
- **관리자 페이지**: PIN 인증, 기록 조회/검색/삭제, 엑셀 내보내기
- **사전 등록 관리**: 소속/부서/인원 CRUD

## 🚀 설치 및 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 SECRET_KEY와 ADMIN_PIN을 변경하세요
```

### 3. 서버 실행

```bash
python app.py
```

브라우저에서 `http://localhost:5000` 접속

## 🔐 관리자 접근

`http://localhost:5000/admin/login` 에서 PIN으로 로그인

기본 PIN: `.env` 파일의 `ADMIN_PIN` 값 (기본값: `1234`)

> ⚠️ 배포 전 반드시 `SECRET_KEY`와 `ADMIN_PIN`을 변경하세요!

## 🗄️ DB 구조

| 테이블 | 설명 |
|---|---|
| `visitors` | 출입자 기록 |
| `affiliations` | 소속 (사전 등록) |
| `departments` | 부서/연구실 (소속 하위) |
| `members` | 인원 (부서 하위) |

## 📁 프로젝트 구조

```
LOG_Kios/
├── app.py              # 메인 서버
├── requirements.txt    # 의존성
├── .env.example        # 환경변수 예시
├── .gitignore
├── templates/          # Jinja2 HTML 템플릿
└── static/             # CSS, JS, 이미지
```
