# IPTV Personal v2.0

Actualización del generador para mejorar la selección automática.

## Qué cambia

- Detección de país mediante `tvg-country` y sufijo de `tvg-id`.
- Chile acepta únicamente señales chilenas.
- Países permitidos por categoría.
- Preferencia por IDs concretos de canales relevantes.
- Mejor control de duplicados.
- Exclusión de señales irrelevantes detectadas en la primera prueba.
- Archivos de depuración en `debug/`.
- Pruebas básicas del generador.

## Instalación

Reemplaza en tu repositorio:

- `config/selection.json`
- `scripts/generate_playlists.py`

Agrega además:

- `tests/test_generator.py`

Después haz Commit y Push. El workflow existente debería ejecutarse automáticamente.

## Resultado esperado

Al terminar aparecerán:

- `playlists/iptv-lite.m3u`
- `playlists/iptv-standard.m3u`
- `playlists/iptv-full.m3u`
- `debug/selection-lite.txt`
- `debug/selection-standard.txt`
- `debug/selection-full.txt`

Los archivos de `debug/` permiten revisar qué canales eligió el algoritmo y por qué.
