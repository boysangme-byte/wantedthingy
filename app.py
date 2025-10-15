import json
from flask import Flask, request, render_template_string, redirect, url_for, flash
from wanted_mailer_auto import run_mailer_once, load_config

app = Flask(__name__)
app.secret_key = "replace-this-in-production"

TEMPLATE = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Wanted Mailer UI</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans KR', Arial, sans-serif; margin: 24px; }
    input, textarea { width: 100%; padding: 8px; margin-top: 6px; }
    .row { max-width: 840px; margin: 0 auto; }
    .actions { display: flex; gap: 8px; margin-top: 12px; }
    .card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin: 12px 0; }
    .preview { border: 1px solid #ddd; padding: 12px; max-height: 420px; overflow: auto; background: #fff; }
    .flash { color: #0a7; margin: 8px 0; }
    .err { color: #c00; margin: 8px 0; }
  </style>
  <script>
    function toArray(value) {
      return value.split(',').map(s => s.trim()).filter(Boolean);
    }
  </script>
  </head>
  <body>
    <div class="row">
      <h1>Wanted Mailer UI</h1>
      {% with messages = get_flashed_messages() %}
        {% if messages %}
          {% for m in messages %}
            <div class="flash">{{ m }}</div>
          {% endfor %}
        {% endif %}
      {% endwith %}

      <form method="post" action="{{ url_for('save_config') }}" class="card">
        <h3>설정</h3>
        <label>수신 이메일
          <input type="email" name="email" value="{{ conf.email }}" required />
        </label>
        <label>지역(콤마로 구분)
          <input type="text" name="locations" value="{{ conf.locations }}" placeholder="서울, 경기" />
        </label>
        <label>직무 키워드(콤마로 구분)
          <input type="text" name="jobs" value="{{ conf.jobs }}" placeholder="개발, 데이터, AI" />
        </label>
        <label>최소 경력(년)
          <input type="number" name="years" value="{{ conf.years }}" min="0" />
        </label>
        <div class="actions">
          <button type="submit">저장</button>
          <a href="{{ url_for('preview') }}">미리보기</a>
          <a href="{{ url_for('send') }}">바로 보내기</a>
        </div>
      </form>

      {% if html %}
      <div class="card">
        <h3>미리보기 ({{ count }}건)</h3>
        <div class="preview">{{ html|safe }}</div>
      </div>
      {% endif %}
    </div>
  </body>
  </html>
"""


def read_conf():
    conf = load_config()
    # 문자열 렌더링용
    return {
        "email": conf.get("email", ""),
        "locations": ", ".join(conf.get("locations", [])),
        "jobs": ", ".join(conf.get("jobs", [])),
        "years": conf.get("years", 0),
    }


@app.get("/")
def index():
    return render_template_string(TEMPLATE, conf=read_conf(), html=None)


@app.get("/preview")
def preview():
    result = run_mailer_once(preview=True)
    return render_template_string(
        TEMPLATE,
        conf=read_conf(),
        html=result.get("html"),
        count=result.get("new_count", 0),
    )


@app.get("/send")
def send():
    result = run_mailer_once(preview=False)
    if result.get("new_count", 0) > 0:
        flash(f"메일 전송 완료: {result['new_count']}건")
    else:
        flash("새 공고가 없습니다.")
    return redirect(url_for("index"))


@app.post("/save")
def save_config():
    email = request.form.get("email", "").strip()
    locations = [s.strip() for s in request.form.get("locations", "").split(",") if s.strip()]
    jobs = [s.strip() for s in request.form.get("jobs", "").split(",") if s.strip()]
    years_raw = request.form.get("years", "0").strip()
    try:
        years = int(years_raw)
    except Exception:
        years = 0

    # 기존 conf를 기반으로 갱신
    conf = load_config()
    conf["email"] = email or conf.get("email", "")
    conf["locations"] = locations or conf.get("locations", [])
    conf["jobs"] = jobs or conf.get("jobs", [])
    conf["years"] = years

    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(conf, f, ensure_ascii=False, indent=2)

    flash("설정을 저장했습니다.")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



