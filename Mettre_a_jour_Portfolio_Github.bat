@echo off
echo Envoi des modifications vers GitHub...
git add .
git commit -m "Mise a jour du portfolio"
git push origin main
echo.
echo Termine ! Tes modifications sont en ligne.
pause
