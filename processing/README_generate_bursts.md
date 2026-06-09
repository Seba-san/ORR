# ✂️ Segmentador Automático de Ráfagas AFSK (`generate_bursts.py`)

Este documento detalla el funcionamiento, arquitectura y flujo de trabajo del script `generate_bursts.py` para la extracción y segmentación automática de ráfagas activas de modulación a partir de grabaciones continuas de audio de telemetría.

---

## 💡 Razón de Ser y Problemática

El transceptor analógico FM (Baofeng UV-82) opera con una máquina de estados de transmisión que fragmenta los datos en ráfagas (bursts) separadas por silencios de enfriamiento (cooldown) para evitar daños térmicos. El receptor graba de forma continua todo el ensayo, generando un único archivo de audio WAV de larga duración que contiene:
1. Ruido de fondo inicial y transitorios de conexión (PTT click).
2. Tono de preámbulo / pre-aviso.
3. Ráfagas de datos reales (AFSK 1200/2400 Hz).
4. Silencios intermedios con **ruido de estática de FM** de gran amplitud si el squelch se abre.
5. Clics de desconexión finales.

La suite de demodulación (`run_suite.py`) está diseñada para analizar el primer bloque activo sostenido. Si procesamos el archivo continuo completo, no podremos evaluar las ráfagas subsiguientes y duplicaremos el análisis de la primera. El script `generate_bursts.py` automatiza la extracción limpia de estas ráfagas de forma inteligente.

---

## 🛠️ Arquitectura y Flujo de Detección

El script procesa cada grabación continua a través de 5 etapas secuenciales de procesamiento digital de señales:

```
    +-------------------------------------------------------------+
    |                Archivo WAV de Entrada Continuo              |
    +-------------------------------------------------------------+
                                   │
                                   ▼
    +-------------------------------------------------------------+
    |       1. Filtro Pasabanda Butterworth (1000 - 2600 Hz)      |
    +-------------------------------------------------------------+
                                   │
                                   ▼
    +-------------------------------------------------------------+
    |       2. Detector de Velocidad de Transmisión (Baudrate)    |
    |      (Calibra tonos y consulta el número de bursts esperado)|
    +-------------------------------------------------------------+
                                   │
                                   ▼
    +-------------------------------------------------------------+
    |          3. Grilla de Búsqueda de Umbral RMS (Grid)         |
    |    (Busca umbrales candidatos de energía entre 0.05 y 0.50) |
    +-------------------------------------------------------------+
                                   │
                                   ▼
    +-------------------------------------------------------------+
    |        4. Validación Espectral AFSK (SNR de Tonos)          |
    |   (Compara la energía a 1200/2400 Hz vs el promedio de ruido)|
    |   Rechaza clics y estática de FM de banda ancha (SNR < 10dB) |
    +-------------------------------------------------------------+
                                   │
                                   ▼
    +-------------------------------------------------------------+
    |             5. Extracción con Padding y Exportación         |
    |        (Aplica 1.0s de margen para preservar preámbulo)     |
    +-------------------------------------------------------------+
```

---

## ⚡ Flujo de Trabajo Integrado

El procesamiento del dataset experimental se simplifica a un flujo de dos comandos:

### Paso 1: Generación de ráfagas
Ejecute el segmentador sobre la carpeta original de grabaciones continuas para generar los archivos de ráfaga limpios en una carpeta temporal:
```bash
python3 ORR/processing/generate_bursts.py data/libre/5 -o data_generated/5 --grid
```

### Paso 2: Demodulación y cálculo de BER
Corra la suite de demodulación directamente sobre la carpeta con las ráfagas generadas:
```bash
python3 ORR/processing/run_suite.py data_generated/5
```

---

## 🎛️ Parámetros de Configuración (CLI)

El script es 100% configurable por consola para evitar la necesidad de alterar el código en el futuro:

| Parámetro | Comando | Valor Defecto | Descripción |
| :--- | :--- | :---: | :--- |
| **Entrada** | *Posicional* | *(Obligatorio)* | Ruta al archivo `.wav` continuo o al directorio que contiene los archivos WAV principales. |
| **Directorio Destino** | `-o` / `--output-dir` | *Mismo origen* | Directorio donde se guardarán las ráfagas extraídas `<basename>_burst_X.wav`. |
| **Margen de Seguridad** | `-p` / `--padding` | `1.0` | Padding de audio en segundos que se añadirá antes y después de cada ráfaga. |
| **Umbral RMS Defecto** | `-t` / `--threshold` | `0.20` | Fracción del RMS de referencia para la detección si no se usa la grilla. |
| **Umbral SNR AFSK** | `--snr-threshold` | `10.0` | Relación de energía lineal mínima del tono Mark/Space vs. ruido de fondo. |
| **Duración Mínima** | `--min-duration` | `4.0` | Duración mínima en segundos que debe durar el bloque activo. |
| **Grilla Automática** | `--grid` | *Desactivado* | Activa la grilla de búsqueda para optimizar el umbral RMS dinámicamente por archivo. |
| **Modo Silencioso** | `-q` / `--quiet` | *Desactivado* | Deshabilita la impresión detallada de la segmentación en consola. |

### Ejemplo de Configuración Avanzada:
Si se trabaja con un canal extremadamente ruidoso, se puede aumentar el umbral SNR y reducir el padding para evitar incluir clicks de squelch adyacentes:
```bash
python3 ORR/processing/generate_bursts.py data/libre/1500 -o data_generated/1500 --grid --snr-threshold 15.0 --padding 0.5
```
