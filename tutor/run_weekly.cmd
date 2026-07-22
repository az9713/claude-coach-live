@echo off
cd /d "%USERPROFILE%\.claude\tutor"
python tutor_weekly.py >> weekly.log 2>&1
