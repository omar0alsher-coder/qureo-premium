import os
import requests
import time
import json
import re
from flask import Flask, request, jsonify, render_template, Response, stream_with_context

app = Flask(__name__)
BASE = "https://me-tp.qureo.education"

# إعدادات البروكسي لـ Railway
PROXIES = {
    'http': 'socks5h://127.0.0.1:1080',
    'https': 'socks5h://127.0.0.1:1080'
}

def get_session(cookies_str):
    session = requests.Session()
    session.proxies.update(PROXIES)
    clean_cookies = cookies_str.replace("\n", "").replace("\r", "").strip()
    if clean_cookies:
        for item in clean_cookies.split(';'):
            if '=' in item:
                key, val = item.strip().split('=', 1)
                session.cookies.set(key, val)
                
    session.headers.update({
        "Content-Type": "application/json",
        "X-Requested-With": "mark.via.gp",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": BASE,
        "Referer": f"{BASE}/",
        "Accept": "*/*"
    })
    return session

def smart_request(session, method, url, max_redirects=10, **kwargs):
    for _ in range(max_redirects):
        try:
            response = session.request(method, url, allow_redirects=False, timeout=15, **kwargs)
        except Exception:
            time.sleep(0.5)
            continue
        if response.status_code in (301, 302, 303, 307, 308):
            redirect_url = response.headers.get("Location", "")
            if not redirect_url: return response
            if redirect_url.startswith("/"): redirect_url = BASE + redirect_url
            elif not redirect_url.startswith("http"): redirect_url = BASE + "/" + redirect_url
            
            if response.status_code in (301, 302, 303):
                method = "GET"; kwargs.pop("json", None); kwargs.pop("data", None)
            url = redirect_url
            continue
        return response
    return response

@app.route("/api/status", methods=["POST"])
def get_status():
    data = request.json
    session = get_session(data.get("cookies", ""))
    
    try:
        u = smart_request(session, "GET", f"{BASE}/api/study/students/me")
        if u.status_code != 200:
            return jsonify({"error": f"فشل الاتصال (HTTP {u.status_code})"}), 400
        user_info = u.json()
        
        d = smart_request(session, "GET", f"{BASE}/api/study/students/courses/javascript_ar/diamond")
        total_diamonds = d.json() if d.status_code == 200 else 0
        
        c = smart_request(session, "GET", f"{BASE}/api/study/students/sections/5/chapters")
        progress = c.json() if c.status_code == 200 else []
        progress_map = {item['chapter_id']: item for item in progress}
        
        chaps_info = smart_request(session, "GET", f"{BASE}/api/study/sections/5")
        q_map = {}
        if chaps_info.status_code == 200:
            for ch in chaps_info.json().get("chapters", []):
                q_map[ch["id"]] = ch.get("question_count", 5)

        chapters = []
        for i in range(1, 43):
            chap_id = 90000 + i
            info = progress_map.get(chap_id, {})
            score = info.get("best_correct_count", 0)
            diamond = info.get("diamond", 0)
            q_count = q_map.get(chap_id, 5)
            
            badge = "RETRY"
            if score == q_count and q_count > 0: badge = "PERFECT"
            elif score > 0: badge = "CLEAR"
                
            chapters.append({
                "id": chap_id, "num": i, "completed": "completed_at" in info,
                "score": score, "total_q": q_count, "diamond": diamond, "badge": badge
            })
            
        return jsonify({
            "user_id": user_info.get("id", ""),
            "name": user_info.get("name", "Student"),
            "total_diamonds": total_diamonds,
            "chapters": chapters
        })
    except Exception as e:
        return jsonify({"error": f"خطأ في الاتصال: {str(e)}"}), 500

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, threaded=True)
