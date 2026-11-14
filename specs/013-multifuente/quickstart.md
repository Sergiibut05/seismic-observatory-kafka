# Quickstart 013

Desde la raíz del repositorio, en PowerShell.

1. `docker compose up --build -d` y esperar a que los siete servicios estén `healthy` (`docker compose ps`). La primera vez, la imagen de la fusión tarda varios minutos (Java, PySpark y el conector de Kafka).
2. Productores: `docker compose logs producer-emsc --since 2m` muestra `result=publicado` con eventos de EMSC; `docker compose logs producer --since 2m`, los de USGS.
3. Fusión: `docker compose logs fusion --since 2m` muestra un `result=lote` cada 15 s con `informes`, `nuevos`, `fusionados` y `emitidos`.
4. Europa en la API: `Invoke-RestMethod "http://127.0.0.1:8000/eventos?limite=5&desde=$((Get-Date).ToUniversalTime().AddDays(-1).ToString('s'))Z"` y comprobar que hay eventos con `fuentes` `emsc`.
5. Relleno (una vez; tarda del orden de una hora): `docker compose run --rm producer python -m observatorio.relleno --desde 2025-01-01 --magnitud-min 2.5`.
6. Panel: `cd frontend; npm start` → la ficha de un terremoto de Europa dice «EMSC», y uno grande de cualquier sitio, «EMSC + USGS».

Evidencias en `evidencias/`.
