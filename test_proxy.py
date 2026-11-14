import requests
import time

print("⏳ جاري اختبار Xray (بورت 1081)...")
time.sleep(3)

proxies = {'http': 'socks5h://127.0.0.1:1081', 'https': 'socks5h://127.0.0.1:1081'}

try:
    r = requests.get('https://me-tp.qureo.education/api/study/students/me', proxies=proxies, timeout=20)
    print(f"✅ الرد: {r.status_code}")
    print(f"📄 المحتوى: {r.text[:200]}")
except Exception as e:
    print(f"❌ فشل: {e}")
