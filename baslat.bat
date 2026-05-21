@echo off
title Kripto Bot Engine & Dashboard Launcher
echo ==================================================
echo          KRIPTO BOT ULTRASAFE LAUNCHER
echo ==================================================
echo.
echo [1/2] Arka plan bot motorunun calisip calismadigi kontrol ediliyor...
echo.

:: Streamlit Dashboard UI baslatiliyor
echo [2/2] Streamlit Dashboard Arayuzu Baslatiliyor...
echo Bu pencere acik kaldigi surece botunuz arka planda 24/7 calismaya devam eder.
echo Pencereyi simge durumuna kucultebilirsiniz ancak kapatmayiniz!
echo.
py -m streamlit run main.py

pause
