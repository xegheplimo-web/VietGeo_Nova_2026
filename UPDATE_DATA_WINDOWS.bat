@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo VIETGEO NOVA - Cap nhat du lieu hanh chinh va OpenStreetMap
where py >nul 2>nul
if errorlevel 1 (echo Vui long cai Python 3.10+; pause & exit /b 1)
py -3 tools\sync_admin.py --force
if errorlevel 1 (echo Co loi khi tai du lieu hanh chinh. & pause & exit /b 1)
echo.
echo Ban sap tai file OSM Viet Nam hang tram MB va nhap POI vao SQLite.
choice /m "Ban co muon tiep tuc"
if errorlevel 2 (echo Da cap nhat hanh chinh. & pause & exit /b 0)
py -3 -m pip install osmium
if errorlevel 1 (echo Khong cai duoc osmium. & pause & exit /b 1)
py -3 tools\download_osm.py --force
if errorlevel 1 (echo Tai OSM that bai. & pause & exit /b 1)
py -3 tools\import_osm.py
pause
