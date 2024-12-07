@echo off
title APIEYE Bot
for /f "delims=#" %%E in ('"prompt #$E# & for %%E in (1) do rem"') do set "\e=%%E"
set cyan=%\e%[96m
set green=%\e%[92m
set purple=%\e%[95m
set red=%\e%[91m
set yellow=%\e%[93m
set reset=%\e%[0m

echo %cyan%Starting script... %date% %time%%reset%

echo %green%Current directory: %cd%%reset%
echo %green%Script path: %~dp0%reset%

if not exist "%~dp0storage\secrets.env" (
    echo %red%ERROR: secrets.env file not found in storage folder.%reset%
    echo %yellow%Creating secrets.env file with default content in storage folder...%reset%
    
    REM
    (
        echo client_id=https://www.reddit.com/prefs/apps
        echo client_secret=https://www.reddit.com/prefs/apps
        echo user_agent=https://www.reddit.com/prefs/apps
        echo cr_api=https://developer.clashroyale.com/
        echo token=https://discord.com/developers/applications
        echo osu_api=https://osu.ppy.sh/home/account/edit#oauth
        echo osu_secret=https://osu.ppy.sh/home/account/edit#oauth
        echo hypixel_api=https://developer.hypixel.net/
    ) > "%~dp0storage\secrets.env"
    
    echo.
    echo %green%The "%~dp0storage\secrets.env" file has been created with the required content.%reset%
    echo %green%Please open the file and make any necessary edits before proceeding.%reset%
    echo.
    echo %cyan%Once you have completed this, press any key to continue...%reset%
    pause >nul
)

echo %cyan%Proceeding with the rest of the script...%reset%

if exist "%~dp0main.py" (
    echo %purple%main.py detected. Proceeding...%reset%

    python --version >nul 2>&1
    if errorlevel 1 (
        echo %red%Python is not installed. Please install Python and try again.%reset%
        pause
        exit /b
    )

    python -m pip install -r "%~dp0requirements.txt"

    echo %green%Starting the bot...%reset%
    start cmd /k python "%~dp0main.py"
    exit /b
)

echo %red%main.py not found.%reset%
echo %yellow%Would you like to clone the repository? (yes/no)%reset%
set /p userInput=Your choice: 

if /i "%userInput%"=="yes" (
    echo %purple%Cloning repository from GitHub...%reset%
    git clone https://github.com/lucasliorle/APEYE --progress
    echo %green%Repository cloned successfully.%reset%
) else (
    echo %green%Skipping repository clone.%reset%
)
pause
