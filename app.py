import os
import requests
import time
import json
import re
from flask import Flask, request, jsonify, render_template, Response, stream_with_context

app = Flask(__name__)
BASE = "https://me-tp.qureo.education"

def get_session(cookies_str):
    session = requests.Session()
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
            response = session.request(method, url, allow_redirects=False, timeout=30, **kwargs)
        except Exception:
            time.sleep(0.2)
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
        if response.status_code == 429:
            time.sleep(1)
            continue
        return response
    return response

def clean_text(text):
    if not text: return ""
    return text.replace("[[bdi]]", "").replace("[[/bdi]]", "").replace("[[bold]]", "").replace("[[/bold]]", "").replace("[[code]]", "").replace("[[/code]]", "").replace("\n", " ").strip()

def solve_two_pass(session, chap_id, questions, test_type, log):
    total = len(questions)
    prefix = "test" if test_type == "test" else "review"
    endpoint = f"{BASE}/api/study/students/{prefix}-questions"
    
    yield log(f"\n🔵 PASS 1/2: إرسال إجابات مبدئية ({total} سؤال)...", "header")
    smart_request(session, "DELETE", f"{BASE}/api/study/students/chapters/{chap_id}/test")
    smart_request(session, "PUT", f"{BASE}/api/study/students/chapters/{chap_id}/test", json={})
    time.sleep(0.3)
    
    for idx, q in enumerate(questions, 1):
        qid, qtype = q["id"], q["type"]
        if qtype == "choice":
            smart_request(session, "PUT", f"{endpoint}/{qid}/answer/choice", json={"choice_id": int(f"{qid}1")})
        else:
            smart_request(session, "PUT", f"{endpoint}/{qid}/answer/description", json={"answer_code": "let _x = 0;"})
        yield log(f"  [{idx}/{total}] Q{qid} — sent dummy", "info")
        time.sleep(0.1) # سرعة الطلقة
        
    time.sleep(0.5)
    yield log("جلب الإجابات الصحيحة من السيرفر...", "info")
    r1 = smart_request(session, "GET", f"{BASE}/api/study/students/chapters/{chap_id}/{prefix}/result")
    answers = {}
    if r1 and r1.status_code == 200:
        result1 = r1.json().get("result", r1.json())
        for cr in result1.get("choice_results", []) or []:
            qid = cr.get("question_id")
            correct = next((c for c in cr.get("choices", []) or [] if c.get("correct")), None)
            if qid and correct and correct.get("choice"): 
                answers[qid] = {"choice_id": correct["choice"]["id"], "text": correct["choice"]["content"]}
        for dr in result1.get("description_results", []) or []:
            qid, ans = dr.get("question_id"), dr.get("model_answer")
            if qid and ans: 
                answers[qid] = {"answer_code": ans}
                
    yield log(f"\n🟢 PASS 2/2: إعادة الجلسة بالإجابات الصحيحة...", "header")
    smart_request(session, "DELETE", f"{BASE}/api/study/students/chapters/{chap_id}/test")
    smart_request(session, "PUT", f"{BASE}/api/study/students/chapters/{chap_id}/test", json={})
    time.sleep(0.3)
    
    solved = 0
    for idx, q in enumerate(questions, 1):
        qid, qtype = q["id"], q["type"]
        if qid in answers:
            ans = answers[qid]
            if qtype == "choice":
                yield log(f"  [{idx}/{total}] Q{qid} ✅ {clean_text(ans.get('text', ''))[:40]}", "success")
                r = smart_request(session, "PUT", f"{endpoint}/{qid}/answer/choice", json={"choice_id": ans["choice_id"]})
                if r and r.status_code == 200: solved += 1
            else:
                yield log(f"  [{idx}/{total}] Q{qid} ✅ إرسال الكود", "success")
                r = smart_request(session, "PUT", f"{endpoint}/{qid}/answer/description", json={"answer_code": ans["answer_code"]})
                if r and r.status_code == 200: solved += 1
        else:
            yield log(f"  [{idx}/{total}] Q{qid} ❌ لم يتم العثور على الإجابة", "error")
        time.sleep(0.1)
        
    yield log("\nالتحقق من النتيجة النهائية...", "info")
    time.sleep(0.5)
    r_final = smart_request(session, "GET", f"{BASE}/api/study/students/chapters/{chap_id}/{prefix}/result")
    final_score = 0
    if r_final and r_final.status_code == 200:
        final_score = r_final.json().get("result", r_final.json()).get("correct_count", 0)
        
    yield log(f"🎉 انتهى! النتيجة: {final_score}/{total}", "success" if final_score == total else "warn")
    return final_score

def solve_chapter_generator(session, chap_id):
    def log(msg, type="info"):
        return f"data: {json.dumps({'msg': msg, 'type': type})}\n\n"

    try:
        yield log(f"جلب بيانات الفصل {chap_id}...", "header")
        r = smart_request(session, "GET", f"{BASE}/api/study/chapters/{chap_id}")
        if not r or r.status_code != 200:
            yield log("فشل جلب الفصل.", "error"); return
        
        data = r.json()
        lectures = data.get("lectures", [])
        test_type = data.get("chapter", {}).get("test_type", "test")
        
        if lectures:
            for lec in lectures:
                lec_id = lec['id']
                yield log(f"\n▶ بدء الدرس: {lec_id}", "header")
                smart_request(session, "PUT", f"{BASE}/api/study/students/lectures/{lec_id}", json={})
                time.sleep(0.1)
                lr = smart_request(session, "GET", f"{BASE}/api/study/lectures/{lec_id}")
                if lr and lr.status_code == 200:
                    for t in lr.json().get('talks', []):
                        if t.get('type') == 'try':
                            try_data = t.get('body', {}).get('codes', [{}])[0]
                            ans = try_data.get('model_answer')
                            lang = try_data.get('lang', 'javascript')
                            if ans:
                                smart_request(session, "PUT", f"{BASE}/api/study/students/lecture-talks/{t['id']}", json={"value": {"try": {"lang": lang, "answer": ans}}})
                                time.sleep(0.1)
                smart_request(session, "PUT", f"{BASE}/api/study/students/lectures/{lec_id}/complete", json={})
                yield log(f"  ✅ تم إنهاء الدرس", "success")
            time.sleep(0.5)

        questions = []
        r = smart_request(session, "GET", f"{BASE}/api/study/chapters/{chap_id}/test")
        if r and r.status_code == 200:
            try:
                q_data = r.json()
                if isinstance(q_data, list):
                    for q in q_data:
                        q_info = q.get("question", {})
                        if q_info.get("id"):
                            questions.append({"id": q_info["id"], "type": q_info["type"]})
            except: pass

        if not questions:
            yield log("لا توجد أسئلة.", "warn"); return

        yield from solve_two_pass(session, chap_id, questions, test_type, log)

    except Exception as e:
        yield log(f"خطأ: {e}", "error")

@app.route("/api/status", methods=["POST"])
def get_status():
    data = request.json
    session = get_session(data.get("cookies", ""))
    
    u = smart_request(session, "GET", f"{BASE}/api/study/students/me")
    if not u or u.status_code != 200:
        return jsonify({"error": "فشل الاتصال، تأكد من الكوكيز"}), 400
    user_info = u.json()
    
    d = smart_request(session, "GET", f"{BASE}/api/study/students/courses/javascript_ar/diamond")
    total_diamonds = d.json() if (d and d.status_code == 200) else 0
    
    c = smart_request(session, "GET", f"{BASE}/api/study/students/sections/5/chapters")
    progress = c.json() if (c and c.status_code == 200) else []
    progress_map = {item['chapter_id']: item for item in progress}
    
    chaps_info = smart_request(session, "GET", f"{BASE}/api/study/sections/5")
    q_map = {}
    if chaps_info and chaps_info.status_code == 200:
        for ch in chaps_info.json().get("chapters", []):
            q_map[ch["id"]] = ch.get("question_count", 5)

    chapters = []
    for i in range(1, 43):
        chap_id = 90000 + i
        info = progress_map.get(chap_id, {})
        score = info.get("best_correct_count", 0)
        q_count = q_map.get(chap_id, 5)
        
        badge = "RETRY"
        if score == q_count and q_count > 0: badge = "PERFECT"
        elif score > 0: badge = "CLEAR"
            
        chapters.append({
            "id": chap_id, "num": i, "completed": "completed_at" in info,
            "score": score, "total_q": q_count, "diamond": info.get("diamond", 0), "badge": badge
        })
        
    return jsonify({
        "user_id": user_info.get("id", ""), "name": user_info.get("name", "Student"),
        "total_diamonds": total_diamonds, "chapters": chapters
    })

@app.route("/api/solve_one", methods=["GET"])
def solve_one():
    cookies = request.args.get('cookies')
    chap_id = int(request.args.get('chapter_id'))
    def generate():
        session = get_session(cookies)
        yield f"data: {json.dumps({'msg': f'🚀 بدء المرحلة {chap_id}...', 'type': 'header'})}\n\n"
        yield from solve_chapter_generator(session, chap_id)
        yield f"data: {json.dumps({'msg': 'DONE', 'type': 'done'})}\n\n"
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route("/api/solve_all", methods=["GET"])
def solve_all():
    cookies = request.args.get('cookies')
    mode = request.args.get('mode', 'all')
    
    def generate():
        session = get_session(cookies)
        c = smart_request(session, "GET", f"{BASE}/api/study/students/sections/5/chapters")
        progress_map = {item['chapter_id']: item for item in (c.json() if c and c.status_code == 200 else [])}
        
        chaps_info = smart_request(session, "GET", f"{BASE}/api/study/sections/5")
        q_map = {}
        if chaps_info and chaps_info.status_code == 200:
            for ch in chaps_info.json().get("chapters", []):
                q_map[ch["id"]] = ch.get("question_count", 5)

        targets = []
        for i in range(1, 43):
            chap_id = 90000 + i
            info = progress_map.get(chap_id, {})
            score = info.get("best_correct_count", 0)
            q_count = q_map.get(chap_id, 5)
            
            if mode == 'perfect':
                if score < q_count: targets.append((chap_id, i))
            else:
                targets.append((chap_id, i))
                
        if not targets:
            yield f"data: {json.dumps({'msg': '🎉 كل المراحل PERFECT بالفعل!', 'type': 'success'})}\n\n"; return

        yield f"data: {json.dumps({'msg': f'🚀 بدء حل {len(targets)} مرحلة...', 'type': 'header'})}\n\n"
        
        for chap_id, chap_num in targets:
            yield f"data: {json.dumps({'msg': f'\n========== المرحلة {chap_num} ==========', 'type': 'header'})}\n\n"
            yield from solve_chapter_generator(session, chap_id)
            time.sleep(0.2)
            
        yield f"data: {json.dumps({'msg': '🎉🎉🎉 انتهى!', 'type': 'done'})}\n\n"
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, threaded=True)
