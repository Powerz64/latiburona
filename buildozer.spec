[app]
title = LaTiburona
package.name = latiburona
package.domain = com.latiburona

source.dir = .
source.include_exts = py,kv,png,jpg,json
source.include_patterns = app/*,kivy_ui/*,requirements.txt,database.db
source.exclude_dirs = .git,.venv,venv,build,dist,__pycache__
source.exclude_patterns = *.pyc,*.pyo,*.log,*.exe

version = 1.0.0

requirements = python3,kivy,requests,sqlite3,urllib3,certifi,charset-normalizer,idna

orientation = portrait
fullscreen = 0

android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.logcat_filters = *:S python:D

presplash_color = #0F172A

[buildozer]
log_level = 2
warn_on_root = 1
