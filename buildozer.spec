[app]
title = Qureo Solver
package.name = qureo
package.domain = org.qureo
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,html,css,js
source.include_patterns = templates/*.html
version = 1.0
requirements = python3,kivy,flask,waitress,requests,urllib3,chardet,idna,certifi
orientation = portrait
fullscreen = 1
android.permissions = INTERNET, VIBRATE, POST_NOTIFICATIONS
android.api = 33
android.minapi = 21
android.ndk = 23b
android.archs = arm64-v8a, armeabi-v7a
p4a.branch = master
