@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title 2025 Trenches Profile Creator
color 0A

:: ===================================================
:: Auto-Elevation: Relaunch script with admin rights if needed
:: ===================================================
net session >nul 2>&1
if %errorlevel% NEQ 0 (
    echo This script requires administrator privileges.
    echo Attempting to relaunch with admin rights...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "Start-Process cmd -ArgumentList '/k \"\"%~f0\"\" --stay' -Verb RunAs"
    exit /b
)

:: ===================================================
:: SETTINGS
:: ===================================================
set "BASE_DIR=%~dp0firefox_profiles"
set "FF_DIR=%ProgramFiles%\Mozilla Firefox"
if not exist "%FF_DIR%\firefox.exe" set "FF_DIR=%ProgramFiles(x86)%\Mozilla Firefox"
set "FIREFOX_BIN=%FF_DIR%\firefox.exe"
set "LINE=============================================================="

:: ===================================================
:: HEADER
:: ===================================================
cls
echo %LINE%
echo.
echo        ████████╗██████╗ ███████╗███╗   ██╗ ██████╗██╗███████╗
echo        ╚══██╔══╝██╔══██╗██╔════╝████╗  ██║██╔════╝██║██╔════╝
echo           ██║   ██████╔╝█████╗  ██╔██╗ ██║██║     ██║███████╗
echo           ██║   ██╔══██╗██╔══╝  ██║╚██╗██║██║     ██║╚════██║
echo           ██║   ██║  ██║███████╗██║ ╚████║╚██████╗██║███████║
echo           ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝ ╚═════╝╚═╝╚══════╝
echo.
echo                  2025  TRENCHES  PROFILE  CREATOR
echo %LINE%
timeout /t 1 >nul

:: ===================================================
:: VERIFY FIREFOX
:: ===================================================
if not exist "%FIREFOX_BIN%" (
  color 0C
  echo [ERROR] Firefox not found in Program Files.
  pause
  exit /b 1
)

:: ===================================================
:: MAIN MENU
:: ===================================================
:MENU
color 0A
cls
echo %LINE%
echo             FIREFOX  PROFILE  CONTROL  PANEL
echo %LINE%
echo.
echo [1]  Create new Firefox profile
echo [2]  Delete existing profile
echo [3]  Exit
echo.
set /p MENU_OPTION=Choose an option (1-3): 

if "%MENU_OPTION%"=="1" goto CREATE_PROFILE
if "%MENU_OPTION%"=="2" goto DELETE_PROFILE
if "%MENU_OPTION%"=="3" goto END
color 0C
echo Invalid choice.
pause
goto MENU

:: ===================================================
:: CREATE PROFILE
:: ===================================================
:CREATE_PROFILE
color 0E
cls
echo %LINE%
echo                 CREATE NEW FIREFOX PROFILE
echo %LINE%
echo.
set /p PROFILE_NAME=Enter profile name: 
if "%PROFILE_NAME%"=="" (
  color 0C
  echo You must enter a name.
  pause
  goto MENU
)

taskkill /IM firefox.exe /F >nul 2>&1
timeout /t 1 >nul

if not exist "%BASE_DIR%" mkdir "%BASE_DIR%"

:: Create timestamp for unique folder
for /f "tokens=1 delims=." %%T in ('powershell -NoProfile -Command "(Get-Date -UFormat %%s)"') do set "TS=%%T"
set "PROFILE_DIR=%BASE_DIR%\%PROFILE_NAME%_%TS%"
mkdir "%PROFILE_DIR%" >nul 2>&1

echo Creating Firefox profile "%PROFILE_NAME%"...
"%FIREFOX_BIN%" -CreateProfile "%PROFILE_NAME% %PROFILE_DIR%" >nul 2>&1
timeout /t 1 >nul

color 0A
echo %LINE%
echo  PROFILE CREATED SUCCESSFULLY
echo  Name:     %PROFILE_NAME%
echo  Location: %PROFILE_DIR%
echo %LINE%
echo.
echo Launching Firefox...
start "" "%FIREFOX_BIN%" -no-remote -profile "%PROFILE_DIR%"
pause
goto MENU

:: ===================================================
:: DELETE PROFILE
:: ===================================================
:DELETE_PROFILE
color 0C
cls
echo %LINE%
echo                 DELETE EXISTING PROFILE
echo %LINE%
echo.

if not exist "%BASE_DIR%" (
  echo No profiles found in %BASE_DIR%
  pause
  goto MENU
)

echo Available profiles:
dir /b "%BASE_DIR%"
echo.
set /p PROFILE_TO_DELETE=Enter folder name to delete: 
if "%PROFILE_TO_DELETE%"=="" (
  echo No name entered.
  pause
  goto MENU
)
set "TARGET_DIR=%BASE_DIR%\%PROFILE_TO_DELETE%"
if not exist "%TARGET_DIR%" (
  echo Profile not found.
  pause
  goto MENU
)

echo Confirm delete (Y/N)?
set /p CONFIRM=
if /I "%CONFIRM%" NEQ "Y" goto MENU
rmdir /s /q "%TARGET_DIR%"
color 0A
echo [OK] Profile deleted.
timeout /t 1 >nul
goto MENU

:: ===================================================
:: EXIT
:: ===================================================
:END
color 0B
cls
echo %LINE%
echo Shutting down 2025 Trenches Profile Creator...
echo Stay low. Stay hidden.
echo %LINE%
timeout /t 2 >nul
exit /b 0
