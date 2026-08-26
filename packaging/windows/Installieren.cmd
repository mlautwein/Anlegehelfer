@echo off
rem ====================================================================
rem Installieren.cmd - Doppelklick genuegt.
rem
rem Startet einrichten.ps1 mit den passenden Schaltern. Der Umweg ueber
rem eine .cmd-Datei ist noetig, weil Windows .ps1-Dateien per Doppelklick
rem nicht ausfuehrt, sondern im Editor oeffnet.
rem ====================================================================
title LIMS-Probenassistent einrichten

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0einrichten.ps1" -Interaktiv
set FEHLER=%ERRORLEVEL%

echo.
if not "%FEHLER%"=="0" (
    echo Die Einrichtung wurde mit Fehlercode %FEHLER% beendet.
    echo Bitte die Meldungen oben lesen - dort steht, was fehlt.
    echo.
)
echo Fenster schliessen mit einer beliebigen Taste.
pause >nul
exit /b %FEHLER%
