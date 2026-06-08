# 🔄 Flujo de Trabajo de Procesamiento con Segmentación Automática (`workflow_bursts.md`)

Este documento detalla el flujo de trabajo integrado para la ingesta, segmentación y demodulación de señales en el proyecto **Outdoor Radio Robotics (ORR)**. Este flujo reemplaza el filtrado manual de archivos mediante el uso del segmentador inteligente de ráfagas (`generate_bursts.py`).

---

## 📌 Contexto y Problemática

El receptor de telemetría en campo graba de forma continua toda la sesión de transmisión. Esto genera archivos `.wav` de larga duración que contienen:
1. Ruido blanco de FM inicial.
2. Tonos de preámbulo/cuenta regresiva del transmisor.
3. **Múltiples ráfagas activas (bursts)** de datos modulados en AFSK separados por silencios de enfriamiento (cooldown) de la radio.
4. Ruido de estática de FM al abrirse el squelch y clics de desconexión (PTT).

Dado que la suite de demodulación (`run_suite.py`) procesa el primer bloque activo sostenido que detecta, pasarle directamente el archivo continuo resulta en la pérdida de las ráfagas secundarias y en métricas distorsionadas. El nuevo flujo automatiza de manera robusta la extracción de estas ráfagas individuales.

---

## 🗺️ Mapa del Flujo de Trabajo Integrado

El flujo de procesamiento digital completo se compone de las siguientes etapas:

```
  [ Grabaciones Continuas ] + [ Telemetría GPS (.csv) ]  <-- Captura en Campo (Web-DAQ)
             │
             ▼
 ┌──────────────────────────────────────────────────────┐
 │ 1. Segmentación Inteligente (generate_bursts.py)    │
 │    • Filtro pasabanda Butterworth (1-2.6 kHz)        │
 │    • Detección automática de baudrate                │
 │    • Optimización de umbral RMS (Búsqueda en Grilla) │
 │    • Validación espectral por SNR de tonos AFSK      │
 └──────────────────────────────────────────────────────┘
             │
             ▼
  [ Ráfagas Segmentadas WAV ] + [ Mapeo de CSVs de GPS ]
             │
             ▼
 ┌──────────────────────────────────────────────────────┐
 │ 2. Demodulación y Análisis (run_suite.py)            │
 │    • Filtro FIR Kaiser (300-3000 Hz)                 │
 │    • Detección y balance dinámico de envolventes      │
 │    • Búsqueda en grilla de fase temporal (DPLL)      │
 │    • Decisión de bit y correlación PRBS-7            │
 └──────────────────────────────────────────────────────┘
             │
             ▼
   [ Reportes BER (%) / Confianza Ck / Perfiles Temporales ]
```

---

## ⚡ Guía de Ejecución Paso a Paso

### Paso 1: Organización del Dataset de Entrada
Ubique los archivos continuos originales grabados del receptor en la estructura estándar de directorios.
Ejemplo:
```
data/libre/
├── 5/
│   ├── audio_sdr_20260604_172254.wav
│   └── audio_sdr_20260604_172254.csv (Telemetría original)
├── 500/
...
```

### Paso 2: Generación Automática de Ráfagas (`generate_bursts.py`)
Ejecute el segmentador automático sobre la carpeta de datos crudos. Se recomienda utilizar el flag `--grid` para que el script determine automáticamente la velocidad de transmisión, busque la cantidad esperada de ráfagas y optimice dinámicamente el umbral RMS de corte por archivo.

```bash
python3 ORR/processing/generate_bursts.py data/libre/5 -o data_generated/5 --grid
```

*Este comando escaneará `data/libre/5`, excluirá archivos que ya posean la nomenclatura de ráfaga y generará los archivos limpios segmentados (`audio_sdr_*_burst_X.wav`) en la carpeta `data_generated/5`.*

### Paso 3: Vinculación de Metadatos GPS de Telemetría (Automática)
Para conservar la trazabilidad de la posición GPS del ensayo y georreferenciar cada ráfaga individual, el segmentador (`generate_bursts.py`) detecta automáticamente si existe un archivo `.csv` de telemetría asociado a la grabación `.wav` principal. 

Si está presente, **copiará y renombrará de forma automática** el archivo de telemetría original (por ejemplo, generando `audio_sdr_..._burst_X.csv` al lado de `audio_sdr_..._burst_X.wav`). **No es necesario ejecutar scripts de terminal adicionales para esta tarea.**

### Paso 4: Ejecución del Demodulador y Medición de BER
Una vez generadas las ráfagas individuales en el directorio destino, invoque la suite de demodulación directamente sobre dicha carpeta:

```bash
python3 ORR/processing/run_suite.py data_generated/5
```

La suite detectará las ráfagas y procesará la secuencia completa de bits transmitidos según la velocidad de cada archivo para generar los reportes de BER y los gráficos de error temporal en la carpeta `reportes/`.

---

## 🎛️ Parámetros de Ingesta Clave en el Segmentador

El script `generate_bursts.py` expone parámetros configurables por línea de comandos para adaptarse a diferentes niveles de ruido de canal sin necesidad de editar el código fuente:

*   `--grid`: **(Recomendado)** Activa la grilla de búsqueda RMS automática. Evalúa umbrales de energía de ráfaga y elige el que reporte la cantidad esperada de ráfagas con la mayor SNR promedio.
*   `--snr-threshold` (Por defecto `10.0` dB): Umbral de validación espectral. Filtra ruidos de estática y clicks de squelch de banda ancha asegurando que el segmento contenga energía concentrada en los tonos Mark ($1200\text{ Hz}$) y Space ($2400\text{ Hz}$).
*   `--padding` (Por defecto `1.0` s): Tiempo de seguridad en segundos agregado antes y después del segmento activo para garantizar que no se trunque el preámbulo de sincronización ni el cierre de la trama.

---

## 📈 Verificación y Aseguramiento de Calidad (QA)

Al procesar un nuevo dataset o integrar el segmentador en el pipeline:
1. **Validación Visual:** Inspeccione los gráficos generados en `reportes/` para corroborar que el enganche de fase (DPLL) y el balance de envolventes se realicen correctamente desde el inicio de la ráfaga.
2. **Consistencia de BER:** Compare las tasas de error de bit obtenidas contra las mediciones de referencia previas (almacenadas en `libre.csv`). Variaciones abruptas en el BER de ráfagas generadas automáticamente pueden indicar un umbral de detección RMS demasiado bajo (que unió ráfagas con silencios) o un padding insuficiente.
