@echo off
setlocal
cd /d "%~dp0"

set PY=python
where python >nul 2>nul || set PY=py

echo.
echo === Installing build tools (one time) ===
%PY% -m pip install --upgrade customtkinter pyinstaller
if errorlevel 1 goto fail

echo.
echo === Building Internship Tracker ===
%PY% -m PyInstaller --noconfirm --clean --onefile --noconsole --name InternshipTracker --icon icon.ico --add-data "icon.ico;." --collect-all customtkinter internship_tracker.py
if errorlevel 1 goto fail

set INSTALL=%LOCALAPPDATA%\Programs\InternshipTracker
set DATA=%APPDATA%\InternshipTracker
set STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs

if not exist "%INSTALL%" mkdir "%INSTALL%"
if not exist "%DATA%" mkdir "%DATA%"

copy /y "dist\InternshipTracker.exe" "%INSTALL%\InternshipTracker.exe" >nul
if errorlevel 1 (
  echo.
  echo Could not copy the app. If Internship Tracker is open, close it and run this again.
  goto fail
)

rem Bring over data from the older version if it's sitting next to this script
if exist "internships.json" if not exist "%DATA%\internships.json" copy "internships.json" "%DATA%\internships.json" >nul

powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%STARTMENU%\Internship Tracker.lnk'); $s.TargetPath='%INSTALL%\InternshipTracker.exe'; $s.IconLocation='%INSTALL%\InternshipTracker.exe'; $s.WorkingDirectory='%INSTALL%'; $s.Save()"

echo.
echo === Done! ===
echo Installed to: %INSTALL%
echo Start Menu shortcut: "Internship Tracker"
echo.
echo To pin it: open the app, right-click its taskbar icon, choose "Pin to taskbar".
echo (Or search "Internship Tracker" in Start, right-click, "Pin to taskbar".)
start "" "%INSTALL%\InternshipTracker.exe"
pause
exit /b 0

:fail
echo.
echo Build failed - see the messages above.
pause
exit /b 1
