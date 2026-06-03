# 💾 *Dataset* Experimental y Telemetría GPS

Esta carpeta contiene los archivos de metadatos de posicionamiento y telemetría de las campañas de ensayo en campo y laboratorio.

> [!IMPORTANT]
> **Acceso a los Archivos de Audio WAV:**
> Debido al tamaño de los archivos de audio crudo digitalizado (cientos de megabytes en total, superando los límites sugeridos de almacenamiento en Git/GitHub), las grabaciones de audio `.wav` se alojan externamente en la siguiente carpeta compartida:
> 
> *   **Enlace de Descarga del *Dataset* Completo:** [*Dataset* de Audio en Google Drive](https://drive.google.com/) *(Nota: Reemplazar por el enlace final de Drive correspondiente).*
> 
> Cada archivo `.csv` aquí presente está indexado por fecha y hora y se corresponde biunívocamente con el archivo de audio `.wav` de idéntico nombre alojado en el Drive.

---

## 📊 Formato de Datos de Telemetría (CSV)

Los archivos `.csv` son generados en tiempo real por el navegador móvil del operador en campo al recibir la señal digitalizada de la Pico 2W. Cada archivo posee la siguiente estructura de metadatos:

| Parámetro | Ejemplo | Descripción |
| :--- | :--- | :--- |
| **Archivo_Audio** | `audio_sdr_20260531_175459.wav` | Nombre del audio WAV capturado asociado a la medición. |
| **Timestamp_Celular_Local** | `2026-05-31T17:54:59-03:00` | Marca temporal local reportada por el dispositivo del operador. |
| **Latitud** | `-31.5128205` | Latitud en grados decimales bajo sistema geodésico WGS-84. |
| **Longitud** | `-68.5082696` | Longitud en grados decimales bajo sistema geodésico WGS-84. |
| **Precision_Metros** | `3.00` | Margen de error horizontal reportado por el chip GPS del celular. |
| **Altitud_Metros** | `644.30` | Altitud elipsoidal en metros sobre el nivel del mar. |
| **Velocidad_M_S** | `0.07` | Velocidad de traslación del celular del operador (m/s). |
| **Rumbo_Grados** | `No disponible` | Dirección de movimiento en grados sexagesimales (si aplica). |
| **Timestamp_GPS_UTC** | `2026-05-31T20:54:59.440Z` | Momento exacto de captura geolocalizada reportada por satélite (UTC). |
| **Dispositivo** | `Navegador Web Movil` | Interfaz física cliente que controló la captura. |
| **Frecuencia_Muestreo_Hz**| `19200` | Tasa de digitalización nominal del ADC de la Pico 2W (Hz). |
| **Muestras_Totales** | `241000` | Cantidad total de muestras de 16 bits en el *buffer* final. |
| **Duracion_Segundos** | `30.125` | Duración temporal exacta calculada en segundos. |
| **Proyecto** | `Intercomunicador SDR - INAUT` | Contexto de investigación del ensayo. |

---

## 🎧 Especificaciones Técnicas del Audio Digitalizado

Las grabaciones de audio crudo obtenidas por el Front-End de recepción analógico y digitalizadas por la Raspberry Pi Pico 2W poseen el siguiente formato unificado:

*   **Formato de Contenedor:** WAVE (cabecera estándar RIFF de 44 bytes).
*   **Frecuencia de Muestreo ($f_s$):** $19200\text{ Hz}$ exactos.
*   **Canales:** 1 (Mono).
*   **Resolución:** 16-bit PCM Signed (Entero con signo centrado en cero).
*   **Rango de Oscilación:** $[-32768, +32767]$ (mapeado de forma unipolar a la oscilación de offset analógico de $1.65\text{ V}$ del ADC).
