import requests, smtplib, json, os, time
from datetime import datetime
from email.mime.text import MIMEText

CONFIG_FILE = "config.json"
LAST_ID_FILE = "last_id.txt"
BASE_URL = "https://www.wanted.co.kr/api/v4/jobs?country=kr&limit=100&job_sort=job.latest_order"

MY_EMAIL = os.environ.get("MY_EMAIL")
MY_PASSWORD = os.environ.get("MY_PASSWORD")

# ===== HTTP 세션 준비 (타임아웃/재시도) =====
def create_http_session(max_retries: int = 3, backoff_seconds: float = 0.8) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "wanted-mailer/1.0 (+https://github.com/)"
    })

    def _get(url: str, timeout: int = 10):
        last_exc = None
        for attempt in range(1, max_retries + 1):
            try:
                resp = session.get(url, timeout=timeout)
                if resp.status_code >= 500:
                    # 서버 오류인 경우 재시도
                    raise requests.HTTPError(f"server error {resp.status_code}")
                return resp
            except Exception as exc:  # requests.RequestException 포함
                last_exc = exc
                wait = backoff_seconds * attempt
                print(f"⚠️ 요청 실패(시도 {attempt}/{max_retries}): {exc} → {wait:.1f}s 대기")
                time.sleep(wait)
        # 마지막 예외를 다시 던짐
        if last_exc:
            raise last_exc

    # 간단 래퍼 할당
    session.get_with_retry = _get  # type: ignore[attr-defined]
    return session

# ===== 설정 로드 =====
def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# ===== 전체 페이지 순회 =====
def fetch_all_jobs(max_pages=20):
    all_jobs = []
    offset = 0
    session = create_http_session()
    while True:
        url = f"{BASE_URL}&offset={offset}"
        try:
            res = session.get_with_retry(url)  # type: ignore[attr-defined]
        except Exception as exc:
            print(f"❌ 요청 실패: {exc}")
            break

        if res.status_code != 200:
            print(f"⚠️ 요청 실패: {res.status_code}")
            break
        try:
            data = res.json()
        except ValueError:
            print("⚠️ JSON 파싱 실패")
            break
        jobs = data.get("data", [])
        if not jobs:
            break
        all_jobs.extend(jobs)
        print(f"📦 {len(all_jobs)}개 로드 중...")
        if len(jobs) < 100 or offset >= max_pages * 100:
            break
        offset += 100
        time.sleep(0.3)
    print(f"✅ 총 {len(all_jobs)}개 공고 로드 완료")
    return all_jobs

# ===== 필터링 =====
def filter_jobs(jobs, conf):
    filtered = []
    for j in jobs:
        address = j.get("address") or {}
        loc = address.get("full_location", "") or ""
        pos = (j.get("position") or "").lower()
        # 경력값 보정: annual_from 없으면 0으로 간주
        yrs = j.get("annual_from")
        if yrs is None:
            yrs = 0
        if any(r in loc for r in conf["locations"]) and \
           any(str(k).lower() in pos for k in conf["jobs"]) and \
           yrs >= conf["years"]:
            filtered.append(j)
    # 최신순 정렬: id 내림차순(원티드 최신 정렬 가정 보강)
    try:
        filtered.sort(key=lambda x: int(x.get("id", 0)), reverse=True)
    except Exception:
        pass
    return filtered

# ===== 마지막 발송 공고 추적 =====
def get_last_id():
    if not os.path.exists(LAST_ID_FILE):
        return None
    with open(LAST_ID_FILE, "r") as f:
        return f.read().strip()

def save_last_id(job_id):
    with open(LAST_ID_FILE, "w") as f:
        f.write(str(job_id))

# ===== 메일 빌드 =====
def build_email(jobs):
    html = f"<h2>📢 {datetime.now().strftime('%m월 %d일')} 새 채용공고 ({len(jobs)}건)</h2><hr>"
    for j in jobs:
        company = (j.get("company") or {}).get("name", "")
        position = j.get("position", "")
        address = (j.get("address") or {}).get("full_location", "")
        reward = (j.get("reward") or {}).get("formatted_total", "N/A")
        jid = j.get("id")
        html += f"""
        <div style='margin-bottom:15px;'>
            <b>{company}</b> - {position}<br>
            📍 {address}<br>
            💰 리워드: {reward}<br>
            <a href='https://www.wanted.co.kr/wd/{jid}' target='_blank'>공고 보기</a>
        </div>
        """
    return html

# ===== 메일 전송 =====
def send_mail(to_email, content):
    if not MY_EMAIL or not MY_PASSWORD:
        raise RuntimeError("이메일 환경변수(MY_EMAIL, MY_PASSWORD)가 설정되지 않았습니다.")
    msg = MIMEText(content, "html")
    msg["Subject"] = f"[원티드 알림] {datetime.now().strftime('%m월 %d일')} 새 공고 업데이트"
    msg["From"] = MY_EMAIL
    msg["To"] = to_email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as smtp:
            smtp.login(MY_EMAIL, MY_PASSWORD)
            smtp.send_message(msg)
        print(f"✅ 메일 발송 완료 → {to_email}")
    except Exception as exc:
        print(f"❌ 메일 발송 실패: {exc}")
        raise

def run_mailer_once(conf: dict | None = None, preview: bool = False):
    """조건에 맞는 신규 공고를 수집하여 미리보기 HTML과 상태를 반환.

    preview=True면 메일 발송/last_id 저장 없이 HTML만 생성해 반환합니다.
    반환값: { 'new_count': int, 'latest_id': str|None, 'html': str|None }
    """
    if conf is None:
        conf = load_config()
    print(f"🎯 조건: 지역={conf['locations']} | 직무={conf['jobs']} | 경력≥{conf['years']}년")

    all_jobs = fetch_all_jobs(max_pages=30)
    jobs = filter_jobs(all_jobs, conf)
    if not jobs:
        print("❌ 조건에 맞는 공고 없음")
        return {"new_count": 0, "latest_id": None, "html": None}

    last_id = get_last_id()
    latest_id = str(jobs[0]["id"]) if jobs else None

    if last_id == latest_id:
        print("📭 새 공고 없음 — 메일 생략")
        return {"new_count": 0, "latest_id": latest_id, "html": None}

    new_jobs = []
    for job in jobs:
        if last_id is not None and str(job.get("id")) == last_id:
            break
        new_jobs.append(job)

    if not new_jobs:
        print("📭 새 공고 없음")
        return {"new_count": 0, "latest_id": latest_id, "html": None}

    html = build_email(new_jobs)

    if preview:
        # 미리보기만 반환
        return {"new_count": len(new_jobs), "latest_id": latest_id, "html": html}

    try:
        send_mail(conf["email"], html)
        if latest_id is not None:
            save_last_id(latest_id)
        return {"new_count": len(new_jobs), "latest_id": latest_id, "html": html}
    except Exception:
        print("⚠️ 메일 발송 또는 저장 단계에서 오류가 발생했습니다.")
        return {"new_count": 0, "latest_id": latest_id, "html": None}


# ===== 실행 =====
if __name__ == "__main__":
    run_mailer_once()
