@echo off
cd /d "%USERPROFILE%\.claude\tutor"
python tutor_blindspot.py >> quarterly.log 2>&1
