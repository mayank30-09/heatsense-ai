Remove-Item Env:PROJ_LIB -ErrorAction SilentlyContinue

$env:PROJ_DATA = (python -c "import pyproj; print(pyproj.datadir.get_data_dir())")

Write-Host "HEATSENSE GIS environment configured."
Write-Host "PROJ_DATA = $env:PROJ_DATA"