@echo off
REM Скрипт для загрузки deploy.sh на VDS и запуска развертывания
REM Использование: upload_and_deploy.bat

echo ================================================
echo   Загрузка и развертывание на VDS
echo ================================================
echo.

SET SERVER=root@45.8.251.77
SET DEPLOY_SCRIPT=deploy.sh

echo [1/3] Копирование скрипта развертывания на сервер...
scp %DEPLOY_SCRIPT% %SERVER%:~/deploy.sh
if %ERRORLEVEL% NEQ 0 (
    echo ОШИБКА: Не удалось скопировать файл на сервер
    echo Проверьте:
    echo - SSH подключение к серверу
    echo - Наличие файла deploy.sh в текущей директории
    pause
    exit /b 1
)

echo.
echo [2/3] Установка прав на выполнение...
ssh %SERVER% "chmod +x ~/deploy.sh"

echo.
echo [3/3] Запуск скрипта развертывания...
echo.
echo ================================================
echo ВНИМАНИЕ: Следуйте инструкциям скрипта!
echo ================================================
echo.

ssh -t %SERVER% "bash ~/deploy.sh"

echo.
echo ================================================
echo Готово!
echo ================================================
echo.
echo Для управления сервисом подключитесь к серверу:
echo   ssh %SERVER%
echo.
echo И используйте команды:
echo   systemctl start bybit-api.service
echo   systemctl status bybit-api.service
echo   journalctl -u bybit-api.service -f
echo.
pause
