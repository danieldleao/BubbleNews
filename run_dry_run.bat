@echo off
chcp 65001 >nul
echo ==============================================================================
echo BUBBLE NEWS - Dry Run (Preview Mode)
echo ==============================================================================
echo.
python run_bubble_news.py --dry-run
echo.
pause
