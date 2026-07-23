# IPTV Personal

Colección personal de canales de televisión gratuitos y públicamente disponibles, generada a partir de [iptv-org](https://github.com/iptv-org/iptv).

## Listas

Una vez ejecutada la automatización:

- **Lite (~50 canales):**  
  `https://raw.githubusercontent.com/antoniocheuque/iptv-personal/main/playlists/iptv-lite.m3u`

- **Standard (~150 canales):**  
  `https://raw.githubusercontent.com/antoniocheuque/iptv-personal/main/playlists/iptv-standard.m3u`

- **Full (~350 canales):**  
  `https://raw.githubusercontent.com/antoniocheuque/iptv-personal/main/playlists/iptv-full.m3u`

La versión Standard está pensada como lista principal. Lite prioriza rapidez para televisores más antiguos. Full incorpora una selección más amplia.

## Enfoque

Las listas priorizan:

- Chile y Latinoamérica.
- Cine y series, preferentemente en español.
- Autos, motores y automovilismo.
- Música.
- Ciencia, espacio y documentales.
- Tecnología, inteligencia artificial, economía y finanzas.
- Inglés permitido especialmente en motor, música, ciencia, tecnología y finanzas.

## Primera puesta en marcha

1. Sube todos los archivos y carpetas de este paquete a la raíz del repositorio.
2. En GitHub abre la pestaña **Actions**.
3. Selecciona **Actualizar listas IPTV**.
4. Pulsa **Run workflow**.
5. Espera entre uno y tres minutos.
6. Comprueba que aparezcan los tres archivos en `playlists/`.

La automatización también se ejecuta los lunes y cada vez que cambian el archivo de configuración o el generador.

## Personalización

Edita `config/selection.json` para cambiar:

- Cantidad de canales.
- Cuotas por categoría.
- Países e idiomas preferidos.
- Palabras prioritarias.
- Palabras excluidas.

Después ejecuta nuevamente el workflow.

## Prueba recomendada

Antes de cargar la lista en el televisor, abre el enlace Raw en **VLC**. Los streams públicos pueden:

- dejar de funcionar;
- tener restricciones geográficas;
- demorar en iniciar;
- cambiar sin aviso;
- no ofrecer EPG.

La inclusión en iptv-org no garantiza estabilidad ni disponibilidad desde Chile.

## Fuente y alcance legal

Este repositorio no contiene video. Genera listas con enlaces que iptv-org identifica como públicamente disponibles. Cada señal conserva sus propios términos, restricciones territoriales y condiciones de uso.
