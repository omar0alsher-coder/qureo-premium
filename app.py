import os
import requests
import time
import json
from flask import Flask, request, jsonify, render_template, Response, stream_with_context

app = Flask(__name__)
BASE = "https://me-tp.qureo.education"

# ❌ تم إزالة البروكسي نهائياً (اتصال مباشر)

def get_session(cookies_str):
    session = requests.Session()
    # لا يوجد بروكسي هنا
    clean_cookies = cookies_str.replace("\n", "").replace("\r", "").strip()
    if clean_cookies:
        for item in clean_cookies.split(';'):
            if '=' in item:
                key, val = item.strip().split('=', 1)
                session.cookies.set(key, val)
                
    session.headers.update({
        "Content-Type": "application/json",
        "X-Requested-With": "mark.via.gp",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        "Origin": BASE,
        "Referer": f"{BASE}/",
        "Accept": "*/*",
        "Accept-Language": "ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7"
    })
    return session

def smart_request(session, method, url, max_redirects=10, **kwargs):
    for _ in range(max_redirects):
        try:
            response = session.request(method, url, allow_redirects=False, timeout=20, **kwargs)
        except Exception:
            time.sleep(1)
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

def clean_text(text):
    if not text: return ""
    return text.replace("[[bdi]]", "").replace("[[/bdi]]", "").replace("[[bold]]", "").replace("[[/bold]]", "").replace("[[code]]", "").replace("[[/code]]", "").replace("\n", " ").strip()

def solve_test_generator(session, chap_id, questions, log):
    total = len(questions)
    yield log(f"\n🔵 PASS 1/2: إرسال إجابات مبدئية ({total} سؤال)...", "header")
    smart_request(session, "PUT", f"{BASE}/api/study/students/chapters/{chap_id}/test")
    time.sleep(1.5)
    
    for idx, q in enumerate(questions, 1):
        qid, qtype, qtext = q["id"], q["type"], clean_text(q.get("content", ""))
        yield log(f"[{idx}/{total}] Q{qid} ({qtype})", "info")
        yield log(f"  السؤال: {qtext[:80]}...", "q")
        
        if qtype == "choice":
            smart_request(session, "PUT", f"{BASE}/api/study/students/test-questions/{qid}/answer/choice", json={"choice_id": int(f"{qid}1")})
        else:
            smart_request(session, "PUT", f"{BASE}/api/study/students/test-questions/{qid}/answer/description", json={"answer_code": "let _x = 0;"})
        time.sleep(0.8)
    
    time.sleep(2)
    yield log("جلب النتيجة لاستخراج الإجابات الصحيحة...", "info")
    r1 = smart_request(session, "GET", f"{BASE}/api/study/students/chapters/{chap_id}/test/result")
    answers = {}
    if r1.status_code == 200:
        result1 = r1.json().get("result", r1.json())
        for cr in result1.get("choice_results", []) or []:
            qid = cr.get("question_id")
            correct = next((c for c in cr.get("choices", []) or [] if c.get("correct")), None)
            if qid and correct and correct.get("choice"): answers[qid] = {"choice_id": correct["choice"]["id"], "text": correct["choice"]["content"]}
        for dr in result1.get("description_results", []) or []:
            qid, ans = dr.get("question_id"), dr.get("model_answer")
            if qid and ans: answers[qid] = {"answer_code": ans}
    
    yield log(f"\n🟢 PASS 2/2: إعادة الجلسة بالإجابات الصحيحة...", "header")
    time.sleep(2)
    smart_request(session, "PUT", f"{BASE}/api/study/students/chapters/{chap_id}/test")
    time.sleep(1.5)
    
    for idx, q in enumerate(questions, 1):
        qid, qtype = q["id"], q["type"]
        if qid in answers:
            ans = answers[qid]
            if qtype == "choice": 
                yield log(f"[{idx}/{total}] Q{qid} ✅ إرسال: {clean_text(ans.get('text', ''))}", "success")
                smart_request(session, "PUT", f"{BASE}/api/study/students/test-questions/{qid}/answer/choice", json={"choice_id": ans["choice_id"]})
            else: 
                yield log(f"[{idx}/{total}] Q{qid} ✅ إرسال الكود: {ans['answer_code'][:50]}...", "success")
                smart_request(session, "PUT", f"{BASE}/api/study/students/test-questions/{qid}/answer/description", json={"answer_code": ans["answer_code"]})
        else:
            yield log(f"[{idx}/{total}] Q{qid} ❌ لم يتم العثور على الإجابة", "error")
        time.sleep(0.8)
    return len(answers)

def solve_review_generator(session, chap_id, questions, log):
    solved = 0
    for idx, q in enumerate(questions, 1):
        qid, qtype, qtext = q["id"], q["type"], clean_text(q.get("content", ""))
        yield log(f"[{idx}/{len(questions)}] Q{qid} ({qtype})", "info")
        yield log(f"  السؤال: {qtext[:80]}...", "q")
        
        if qtype == "choice":
            r = smart_request(session, "PUT", f"{BASE}/api/study/students/review-questions/{qid}/answer/choice", json={"choice_id": int(f"{qid}1")})
            if r and r.status_code == 200:
                choices = r.json().get('result', {}).get('choices', [])
                correct = next((c for c in choices if c.get('correct')), None)
                if correct:
                    yield log(f"  ↳ الإجابة الصحيحة: {clean_text(correct['choice']['content'])}", "a")
                    smart_request(session, "PUT", f"{BASE}/api/study/students/review-questions/{qid}/answer/choice", json={"choice_id": correct['choice']['id']})
                    yield log(f"  ✅ تم إرسال الإجابة", "success")
                    solved += 1; time.sleep(0.5); continue
        else:
            r = smart_request(session, "PUT", f"{BASE}/api/study/students/review-questions/{qid}/answer/description", json={"answer_code": "let _x = 0;"})
            if r and r.status_code == 200:
                model_answer = r.json().get('result', {}).get('model_answer')
                if model_answer:
                    yield log(f"  ↳ الكود الصحيح: {model_answer}", "a")
                    smart_request(session, "PUT", f"{BASE}/api/study/students/review-questions/{qid}/answer/description", json={"answer_code": model_answer})
                    yield log(f"  ✅ تم إرسال الكود", "success")
                    solved += 1; time.sleep(0.5); continue
        yield log(f"  ⚠️ لم يُحل", "warn")
        time.sleep(0.5)
    return solved

def solve_chapter_generator(session, chap_id):
    def log(msg, type="info"):
        return f"data: {json.dumps({'msg': msg, 'type': type})}\n\n"

    try:
        yield log(f"جلب بيانات الفصل {chap_id}...", "header")
        r = smart_request(session, "GET", f"{BASE}/api/study/chapters/{chap_id}")
        if r.status_code != 200:
            yield log(f"فشل جلب الفصل (HTTP {r.status_code}). تأكد من صلاحية الكوكيز.", "error")
            return
        
        data = r.json()
        lectures = data.get("lectures", [])
        test_type = data.get("chapter", {}).get("test_type", "test")
        
        yield log(f"النوع: {test_type} | الدروس: {len(lectures)}", "info")
        
        if lectures:
            for lec in lectures:
                lec_id = lec['id']
                yield log(f"\n▶ بدء الدرس: {lec_id}", "header")
                smart_request(session, "PUT", f"{BASE}/api/study/students/lectures/{lec_id}")
                time.sleep(0.5)
                lr = smart_request(session, "GET", f"{BASE}/api/study/lectures/{lec_id}")
                if lr.status_code == 200:
                    for t in lr.json().get('talks', []):
                        if t.get('type') == 'try':
                            try_data = t.get('body', {}).get('codes', [{}])[0]
                            ans = try_data.get('model_answer')
                            q_text = clean_text(t.get('body', {}).get('question', {}).get('text', ''))
                            lang = try_data.get('lang', 'javascript')
                            
                            if ans:
                                yield log(f"  Q: {q_text[:60]}...", "q")
                                yield log(f"  A: {ans[:60]}...", "a")
                                smart_request(session, "PUT", f"{BASE}/api/study/students/lecture-talks/{t['id']}", json={"value": {"try": {"lang": lang, "answer": ans}}})
                                time.sleep(0.5)
                smart_request(session, "PUT", f"{BASE}/api/study/students/lectures/{lec_id}/complete")
                yield log(f"  ✅ تم إنهاء الدرس {lec_id}", "success")
                time.sleep(0.5)
            yield log("انتظار السيرفر لتحديث الحالة (3 ثواني)...", "info")
            time.sleep(3)

        yield log("\nجلب قائمة الأسئلة...", "info")
        questions = []
        r = smart_request(session, "GET", f"{BASE}/api/study/chapters/{chap_id}/test")
        if r.status_code == 200 and isinstance(r.json(), list):
            for q in r.json():
                q_info = q.get("question", {})
                if q_info.get("id"): 
                    questions.append({
                        "id": q_info["id"], 
                        "type": q_info["type"],
                        "content": q_info.get("content", "")
                    })

        if not questions:
            yield log("لم يتم العثور على أسئلة.", "warn")
            return

        smart_request(session, "PUT", f"{BASE}/api/study/students/chapters/{chap_id}/test")
        time.sleep(1)

        if test_type == "test":
            yield from solve_test_generator(session, chap_id, questions, log)
            yield log(f"🎉 انتهى الاختبار!", "success")
        else:
            solved = yield from solve_review_generator(session, chap_id, questions, log)
            yield log(f"🎉 انتهت المراجعة! صحيحة: {solved}/{len(questions)}", "success")

    except Exception as e:
        yield log(f"خطأ غير متوقع: {e}", "error")

@app.route("/api/status", methods=["POST"])
def get_status():
    data = request.json
    session = get_session(data.get("cookies", ""))
    
    u = smart_request(session, "GET", f"{BASE}/api/study/students/me")
    if u.status_code != 200:
        return jsonify({"error": f"فشل الاتصال (HTTP {u.status_code}). الكوكيز منتهية أو تم حظر السيرفر."}), 400
    user_info = u.json()
    
    d = smart_request(session, "GET", f"{BASE}/api/study/students/courses/javascript_ar/diamond")
    total_diamonds = d.json() if d.status_code == 200 else 0
    
    c = smart_request(session, "GET", f"{BASE}/api/study/students/sections/5/chapters")
    progress = c.json() if c.status_code == 200 else []
    progress_map = {item['chapter_id']: item for item in progress}
    
    chapters_meta = smart_request(session, "GET", f"{BASE}/api/study/sections/5")
    chap_meta_map = {}
    if chapters_meta.status_code == 200:
        for ch in chapters_meta.json().get("chapters", []):
            chap_meta_map[ch["id"]] = ch.get("question_count", 5)

    chapters = []
    for i in range(1, 43):
        chap_id = 90000 + i
        info = progress_map.get(chap_id, {})
        best_score = info.get("best_correct_count", 0)
        diamond = info.get("diamond", 0)
        completed = "completed_at" in info
        q_count = chap_meta_map.get(chap_id, 5)
        
        badge = "RETRY"
        if best_score >= q_count and best_score > 0: badge = "PERFECT"
        elif best_score > 0: badge = "CLEAR"
            
        chapters.append({
            "id": chap_id,
            "num": i,
            "completed": completed,
            "score": best_score,
            "total_q": q_count,
            "diamond": diamond,
            "badge": badge
        })
        
    return jsonify({
        "user_id": user_info.get("id", ""),
        "name": user_info.get("name", "Student"),
        "total_diamonds": total_diamonds,
        "chapters": chapters
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
        progress_map = {item['chapter_id']: item for item in c.json()} if c.status_code == 200 else {}
        
        chapters_meta = smart_request(session, "GET", f"{BASE}/api/study/sections/5")
        chap_meta_map = {}
        if chapters_meta.status_code == 200:
            for ch in chapters_meta.json().get("chapters", []):
                chap_meta_map[ch["id"]] = ch.get("question_count", 5)

        targets = []
        for i in range(1, 43):
            chap_id = 90000 + i
            info = progress_map.get(chap_id, {})
            best_score = info.get("best_correct_count", 0)
            q_count = chap_meta_map.get(chap_id, 5)
            
            if mode == 'perfect':
                if best_score < q_count:
                    targets.append((chap_id, i))
            else:
                targets.append((chap_id, i))
                
        if not targets:
            yield f"data: {json.dumps({'msg': '🎉 كل المراحل PERFECT بالفعل!', 'type': 'success'})}\n\n"
            return

        yield f"data: {json.dumps({'msg': f'🚀 بدء حل {len(targets)} مرحلة (وضع: {mode})...', 'type': 'header'})}\n\n"
        
        for chap_id, chap_num in targets:
            yield f"data: {json.dumps({'msg': f'\n========== المرحلة {chap_num} ==========', 'type': 'header'})}\n\n"
            yield from solve_chapter_generator(session, chap_id)
            time.sleep(2)
            
        yield f"data: {json.dumps({'msg': '🎉🎉🎉 انتهى حل جميع المراحل المطلوبة!', 'type': 'done'})}\n\n"
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), threaded=True)
