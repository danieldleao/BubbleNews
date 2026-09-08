@echo off
chcp 65001 >nul
echo ==============================================================================
echo BUBBLE NEWS - Setup and Dependency Verification
echo ==============================================================================
echo.

:: Check Python availability
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found on PATH. Please install Python 3.10+ and add it to PATH.
    pause
    exit /b 1
)

echo [1/3] Checking and installing Python dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install requirements.
    pause
    exit /b 1
)
echo [OK] Dependencies installed successfully.
echo.

echo [2/3] Checking environment configuration...
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [INFO] Created .env from .env.example.
        echo [ACTION REQUIRED] Please edit .env to add your Gemini API Key and Disroot credentials.
    ) else (
        echo [WARN] .env.example not found.
    )
) else (
    echo [OK] .env configuration file found.
)
echo.

echo [3/3] Running dry-run validation test...
python run_bubble_news.py --dry-run
echo.
echo ==============================================================================
echo Setup completed!
echo - To configure secrets: edit the .env file
echo - To run a test: execute run_dry_run.bat
echo - To run full pipeline: execute run.bat
echo ==============================================================================
pause
