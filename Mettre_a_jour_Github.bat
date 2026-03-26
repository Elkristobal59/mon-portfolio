@echo off
echo Envoi des modifications vers GitHub...
git add index.html
git commit -m "Mise a jour de index.html SITE CHRIS"
git push origin main
echo.
echo Termine ! Tes modifications sont en ligne.
pause
