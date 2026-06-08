# 💾 *Dataset* Experimental y Telemetría GPS

Esta carpeta contiene los archivos de metadatos de posicionamiento y telemetría de las campañas de ensayo en campo y laboratorio de la plataforma **ORR**.

> [!IMPORTANT]
> **Acceso a los Archivos de Audio WAV:**
> Debido al tamaño de los archivos de audio crudo digitalizado (cientos de megabytes en total, superando los límites sugeridos de almacenamiento en Git/GitHub), las grabaciones de audio `.wav` se alojan externamente en la siguiente carpeta compartida:
> 
> *   **Enlace de Descarga del *Dataset* Completo (Google Drive):** [Bases de Datos de Audio ORR](https://drive.google.com/drive/folders/1wKw8cH1Ox6S6E19gmR8-GltFr6CDUwmw?usp=sharing)
> 
> Cada archivo `.csv` aquí presente está indexado por fecha y hora y se corresponde biunívocamente con el archivo de audio `.wav` de idéntico nombre alojado en el Drive.

---

## 📂 Distribución de la Base de Datos

La base de datos en Google Drive y los metadatos en el repositorio están organizados en dos grandes conjuntos según el entorno y la metodología de ensayo:

1. **`campo/` (Ensayos de Campo):**
   * Contiene las mediciones experimentales obtenidas bajo follaje real en un olivar de producción intensiva en la provincia de San Juan, Argentina.
   * Se operó con una potencia de $1.0\text{ W}$ (Low Power del transceptor Baofeng UV-82) en la frecuencia de UHF de $433\text{ MHz}$ con polarización horizontal.
   * Las mediciones cubren distancias de hasta 1500 metros bajo condiciones severas de obstrucción por biomasa húmeda y copas de árboles adultos.

2. **`libre/` (Ensayos en Línea de Vista / Campo Libre):**
   * Contiene los registros correspondientes a mediciones de calibración en espacio libre (laboratorio y campo abierto con línea de vista directa).
   * Se encuentra subdividido en carpetas según la distancia física (en metros) entre el transmisor y el receptor:
     * `5/`: Calibración y pruebas a corta distancia (5 metros).
     * `500/`: Pruebas a media distancia en línea de vista (500 metros).
     * `1000/`: Pruebas a larga distancia con obstrucción mínima (1000 metros).
     * `1500/`: Pruebas de límite de enlace en campo libre (1500 metros).

---

## 🏷️ Significado de los Nombres de Archivos

Los archivos siguen una nomenclatura estandarizada que garantiza la trazabilidad temporal y espacial:

`audio_sdr_YYYYMMDD_HHMMSS.[wav|csv]`

Donde:
* **`audio_sdr`**: Prefijo identificador del sistema de adquisición digitalizado.
* **`YYYYMMDD`**: Fecha de la captura (Año, Mes, Día) reportada por el dispositivo del operador.
* **`HHMMSS`**: Hora de la captura (Hora, Minuto, Segundo) en tiempo local del operador.

### Correspondencia Biunívoca (1-a-1)
* El archivo `.wav` (audio crudo) y el archivo `.csv` (metadatos) que poseen el mismo timestamp se corresponden exactamente a la misma medición física.
* **Archivos con sufijo `_burst_X.wav`** (ej. `audio_sdr_20260604_180700_burst_1.wav`): Son segmentos de audio extraídos de la grabación continua correspondientes a ráfagas individuales de transmisión útiles, recortados y procesados de manera *offline* mediante la suite de demodulación.

---

## ⚙️ Metodología de Grabación (Receptor RX / Web-DAQ)

Las grabaciones de audio analógico del receptor de radio FM se digitalizan empleando un microcontrolador **Raspberry Pi Pico 2W** configurado como un adquisidor de datos inalámbrico (Web-DAQ). El flujo de grabación opera de la siguiente manera:

1. **Adquisición Analógica de Alta Precisión (Core 1):**
   * El microcontrolador ejecuta MicroPython sobre el chip RP2350 overclockeado a $150\text{ MHz}$ para inmunizar los lazos de tiempo críticos.
   * En el **Core 1**, un timer por hardware lee la entrada analógica `GP26` (ADC0) a una tasa fija y estable de **$19200\text{ Hz}$** ($f_s$).
   * Para anular la latencia y las derivas de tiempo inducidas por el recolector de basura (*garbage collector*), se preasigna un esquema de doble búfer (*ping-pong*) de un segundo de duración ($19200$ muestras) y se deshabilita temporalmente el *Garbage Collector* en caliente con `gc.disable()`.
   * El offset analógico unipolar de $1.65\text{ V}$ de la placa se remueve restando $32768$ a la lectura directa de 16 bits sin signo del ADC, produciendo muestras de **16-bit PCM Signed** (con valores en el rango $[-32768, +32767]$).

2. **Transmisión de Datos por Wi-Fi (Core 0):**
   * El **Core 0** levanta un Punto de Acceso Wi-Fi local de nombre `PicoSDR` (IP `192.168.4.1`, puerto 80).
   * El operador se conecta con su teléfono celular y accede al panel web (HTML/JS) servido en bloques pequeños (*chunked*) por el microcontrolador.
   * Al conectar, el navegador inicia una conexión persistente al *endpoint* de streaming TCP `/stream`. El Core 0 de la Pico 2W transmite los buffers PCM de Core 1 a través del socket de forma inalámbrica.

3. **Almacenamiento y Telemetría en el Cliente (Navegador Móvil):**
   * **Visualización en Tiempo Real:** El script JavaScript en el navegador calcula la transformada rápida de Fourier para el VU-meter, evaluando la densidad espectral en la frecuencia del tono de Mark ($1200\text{ Hz}$) para filtrar la estática del silenciador de la radio.
   * **Registro GPS Activo:** El celular obtiene de forma continua la posición GPS por hardware en modo de alta precisión.
   * **Descarga Simultánea:** Al pulsar "Detener y Guardar", el script de JavaScript en el navegador empaqueta las muestras PCM acumuladas en la memoria RAM, inyecta una **cabecera estándar RIFF/WAVE de 44 bytes** y genera la descarga automática y simultánea del archivo de audio `.wav` y del archivo de telemetría `.csv` con la información del GPS y del canal.

---

## 📡 Estructura y Parámetros de la Secuencia Transmitida (TX)

Para caracterizar el canal y analizar la tasa de error de bit (BER), el transmisor (TX) genera secuencias balanceadas deterministas de datos digitales.

### Generación de la Secuencia PRBS-7
El firmware del transmisor implementa un Registro de Desplazamiento con Retroalimentación Lineal (**LFSR** — *Linear Feedback Shift Register*) con arquitectura Fibonacci:
* **Polinomio generador:** $x^7 + x^6 + 1$ (Polinomio característico de Golomb, 1982).
* **Recurrencia:** $y(n) = y(n-6) \oplus y(n-7)$.
* **Semilla inicial (*Seed*):** `0x7F` (todos los bits en $1$). El estado `0x00` está estrictamente prohibido por ser un punto fijo muerto.
* **Longitud maximal:** $2^7 - 1 = 127$ bits.
* **Propiedades estadísticas:** Contiene exactamente 64 unos y 63 ceros. Incluye rachas de hasta 7 bits idénticos consecutivos para estresar el recuperador de fase y de reloj del receptor.

### Modulación y Frecuencias AFSK
La secuencia binaria es modulada en audio analógico mediante **AFSK** (*Audio Frequency Shift Keying*) con fase continua (CPFSK) sintetizada en la Pico 2W mediante DDS (Direct Digital Synthesis) mapeado a PWM de hardware a $125\text{ kHz}$:
* **Mark (Bit Lógico 1):** Tono senoidal de **$1200\text{ Hz}$**.
* **Space (Bit Lógico 0):** Tono senoidal de **$2400\text{ Hz}$**.
* **Velocidades de prueba (Baudrates):** El sistema rota cíclicamente entre 10, 50, 150, 300, 600 y 1200 baudios.

### Protección Térmica y Fragmentación de Ensayos
Para que los resultados sean estadísticamente robustos, cada punto de medición requiere recibir un volumen total de **$12700\text{ bits}$** ($100$ ciclos PRBS-7 completos). Sin embargo, el paso final de potencia RF del transceptor portátil Baofeng UV-82 no está diseñado para transmisión digital continua de largo aliento. 

Para evitar daños térmicos y sobrecalentamiento, se limita la transmisión continua por ráfaga a un máximo de **30 segundos**. Por ello, el volumen de bits de ensayo se fragmenta en ráfagas (*bursts*) con pausas obligatorias de enfriamiento (Duty Cycle $\le 50\%$):

| Velocidad (bd) | Bits por Ráfaga | Cantidad de Ráfagas | Duración Activa TX | Pausa de Enfriamiento (s) | Comentarios |
| :---: | :---: | :---: | :---: | :---: | :--- |
| **10 bd** | 127 | 1 | ~12.7 s | 30 s | Modificado para evitar excesiva duración térmica a velocidad lenta. |
| **50 bd** | 1270 | 2 | ~25.4 s | 27 s | Fragmentado en 2 ráfagas de 10 ciclos PRBS-7 cada una. |
| **150 bd** | 3175 | 2 | ~21.1 s | 23 s | Fragmentado en 2 ráfagas de 25 ciclos PRBS-7 cada una. |
| **300 bd** | 6350 | 2 | ~21.1 s | 23 s | Fragmentado en 2 ráfagas de 50 ciclos PRBS-7 cada una. |
| **600 bd** | 12700 | 1 | ~21.1 s | 23 s | Ráfaga única de 100 ciclos PRBS-7. |
| **1200 bd** | 12700 | 1 | ~10.6 s | 12 s | Ráfaga única de 100 ciclos PRBS-7. |

*Nota:* Los tiempos de transmisión activa reales del PTT incluyen 1.0s de pre-delay (para la apertura de squelch en RX) y 1.0s de post-delay (para asegurar la salida física del búfer de audio antes de soltar el PTT).

---

## 📊 Formato de Datos de Telemetría (CSV)

Cada archivo `.csv` descargado de forma inalámbrica posee la siguiente estructura de metadatos:

| Parámetro | Ejemplo | Descripción |
| :--- | :--- | :--- |
| **Archivo_Audio** | `audio_sdr_20260606_135923.wav` | Nombre del audio WAV capturado asociado a la medición. |
| **Timestamp_Celular_Local** | `2026-06-06T13:59:23-03:00` | Marca temporal local reportada por el dispositivo del operador. |
| **Latitud** | `-31.5423918` | Latitud en grados decimales bajo sistema geodésico WGS-84. |
| **Longitud** | `-68.6092303` | Longitud en grados decimales bajo sistema geodésico WGS-84. |
| **Precision_Metros** | `3.00` | Margen de error horizontal reportado por el chip GPS del celular. |
| **Altitud_Metros** | `719.30` | Altitud elipsoidal en metros sobre el nivel del mar. |
| **Velocidad_M_S** | `0.07` | Velocidad de traslación del celular del operador (m/s). |
| **Rumbo_Grados** | `No disponible` | Dirección de movimiento en grados sexagesimales (si aplica). |
| **Timestamp_GPS_UTC** | `2026-06-06T16:59:22.645Z` | Momento exacto de captura geolocalizada reportada por satélite (UTC). |
| **Dispositivo** | `Navegador Web Movil` | Interfaz física cliente que controló la captura. |
| **Frecuencia_Muestreo_Hz**| `19200` | Tasa de digitalización nominal del ADC de la Pico 2W (Hz). |
| **Muestras_Totales** | `806400` | Cantidad total de muestras de 16 bits en el *buffer* final. |
| **Duracion_Segundos** | `42.000` | Duración temporal exacta calculada en segundos. |
| **Proyecto** | `Intercomunicador SDR - INAUT (UNSJ)` | Contexto de investigación del ensayo. |
