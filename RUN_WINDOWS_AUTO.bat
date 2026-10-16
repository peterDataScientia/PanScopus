@echo off
setlocal
cd /d "%~dp0"
echo PanScopus - Windows Chrome automated Scopus CSV export
echo.
where python >nul 2>&1
if errorlevel 1 (
  echo Python is not on PATH. Open this folder in your existing Python/Conda environment.
  pause
  exit /b 1
)
python -c "import selenium" >nul 2>&1
if errorlevel 1 (
  echo Installing free Selenium dependency...
  python -m pip install "selenium>=4.25,<5"
  if errorlevel 1 (
    echo Selenium installation failed. Check Python and your internet connection.
    pause
    exit /b 1
  )
)
python run_windows_auto.py
set EXITCODE=%ERRORLEVEL%
echo.
if %EXITCODE% NEQ 0 echo PanScopus stopped with error %EXITCODE%.
echo CSV files are saved in this folder's exports directory.
pause
exit /b %EXITCODE%
