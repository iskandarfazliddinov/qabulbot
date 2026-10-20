@echo off
cd /d "%~dp0"
where python >nul 2>nul || (echo PYTHON TOPILMADI. Microsoft Store orqali Python o'rnating. & pause & exit)
python -m pip install -q -r requirements.txt
echo.
echo  Bot ishlayapti. Oynani yopmang! To'xtatish: Ctrl+C
echo.
python bot.py
pause
