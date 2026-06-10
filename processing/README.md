# 📊 Suite de Procesamiento y Demodulación *Offline*

Esta carpeta contiene la suite de herramientas desarrolladas en **Python** para la demodulación síncrona *offline* y la caracterización espectral de las señales de audio AFSK capturadas por el Web-DAQ.

---

## 🚀 Flujo del Procesamiento Digital de Señales (DSP)

El software realiza el procesamiento en seis etapas secuenciales de bajo nivel. A partir del paso 3, el pipeline se **bifurca** según la velocidad de símbolo detectada para compensar las características específicas de cada régimen de baudios:

```
                  +-----------------------------------+
                  |      Archivo WAV de Entrada       |
                  +-----------------------------------+
                                    │
                                    ▼
                  +-----------------------------------+
                  |  Filtro FIR Kaiser (300-3000 Hz)  |
                  +-----------------------------------+
                                    │
                                    ▼
                  +-----------------------------------+
                  |  Analizador Fourier (Autotuning)  |
                  +-----------------------------------+
                                    │
                   ┌────────────────┴─────────────────┐
                   │ baud = 1200                      │ baud ≤ 600
                   ▼                                  ▼
        +--------------------+             +--------------------+
        |  Filtros Pasa-Banda|             |  Filtros Pasa-Banda|
        |  Butterworth       |             |  Butterworth       |
        |  (filtfilt,        |             |  (lfilter,         |
        |   ZERO-PHASE)      |             |   causal)          |
        +--------------------+             +--------------------+
                   │                                  │
                   ▼                                  ▼
        +--------------------+             +--------------------+
        | Envolventes +      |             | Envolventes +      |
        | LP Zero-Phase      |             | LP Causal          |
        +--------------------+             +--------------------+
                   │                                  │
                   ▼                                  │
        +--------------------+                       │
        | Normalización      |                       │
        | Geométrica Absoluta|                       │
        | (centro p5-p95)    |                       │
        +--------------------+                       │
                   │                                  │
                   ▼                                  │
        +--------------------+                       │
        | Squelch de Inicio  |                       │
        | (primer pulso >0.5)|                       │
        +--------------------+                       │
                   └────────────────┬─────────────────┘
                                    │
                                    ▼
                  +-----------------------------------+
                  | Búsqueda de Fase (Grid Search)    |
                  | + DPLL (Kp/Ki desde config.py)    |
                  +-----------------------------------+
                                    │
                                    ▼
                  +-----------------------------------+
                  |    Cálculo de BER y Confianza     |
                  +-----------------------------------+
```

1.  **Acondicionamiento (Filtro FIR Kaiser):** Un filtro de respuesta al impulso finita (FIR) de fase lineal de orden 127 aísla la banda útil (300 Hz a 3000 Hz), eliminando ruidos fuera de banda tales como zumbidos de red de 50/60 Hz.
2.  **Autocalibración Espectral (Transformada Rápida de Fourier):** Ejecuta una transformada rápida de Fourier para detectar las frecuencias reales del transmisor (Mark y Space), compensando corrimientos locales debidos a derivas térmicas de los osciladores.
3.  **Filtros de Banda Adaptativos (bifurcado):**
    - **1200 bd:** Usa `signal.filtfilt()` (fase nula, retardo de grupo cero) tanto en los filtros pasa-banda como en el filtro pasa-bajos de envolvente. Esto elimina el retardo de grupo de ~8.8 muestras que causaba ISI sistemático a 1200 bd con el método causal.
    - **≤ 600 bd:** Usa `signal.lfilter()` causal clásico, que funciona correctamente a estas velocidades donde el retardo de grupo es despreciable en proporción al período de símbolo.
4.  **Detección y Balance de Envolvente:** Estima las envolventes de amplitud y aplica un factor de ganancia $g$ para compensar la atenuación diferencial de frecuencia: $y_{\text{cruda}} = env_{\text{mark}} - g \cdot env_{\text{space}}$. Para 1200 bd, se aplica adicionalmente:
    - **Normalización Geométrica Absoluta:** La señal se normaliza al rango $[-1, +1]$ usando el punto medio exacto entre el percentil 5 y 95 del burst ($y = (y_{\text{cruda}} - c) / a$, con $c$ el centro y $a$ la semiplitud), robusta frente a tramas asimétricas.
    - **Squelch de Inicio:** Se detecta el primer pulso real ($|y| > 0.5$) y se reposiciona `bloque_inicio` exactamente un símbolo antes de él, evitando el falso enganche del reloj (*false lock*) sobre el silencio inicial.
5.  **Búsqueda de Fase y Sintonización DPLL:** Realiza una búsqueda en rejilla (*Grid Search*) de la fase temporal inicial. Para 1200 bd, la ventana de búsqueda se amplía a $15 \times N_s$ muestras para compensar el retardo residual de la cadena de filtros. A continuación, el DPLL se sintoniza también por grilla sobre los candidatos de $K_p$ y $K_i$ definidos en `config.DPLL_KP_CANDIDATOS` y `config.DPLL_KI_CANDIDATOS`. El período de símbolo $N_s = f_s / \text{baud}$ se calcula siempre dinámicamente, sin valores hardcodeados por velocidad.
6.  **Evaluación de BER:** Alinea la secuencia demodulada mediante correlación cruzada contra el patrón local PRBS-7 de 127 bits de Golomb ($y(n) = y(n-6) \oplus y(n-7)$) y calcula la Tasa de Error de Bit (BER) sobre la ráfaga completa.

---

## 🛠️ Instalación de Dependencias

Se requiere tener instalado **Python 3.10+** en el sistema. Para instalar los requisitos matemáticos necesarios, ejecuta:

```bash
pip install -r requirements.txt
```

---

## ⚡ Ejecución del Pipeline Completo

El pipeline de procesamiento se divide en **tres etapas auditables e independientes**:

1. **Segmentar** los audios continuos en ráfagas individuales → `generate_bursts.py`
2. **Demodular** cada ráfaga y medir el BER → `run_suite.py`
3. **Consolidar** los resultados en un CSV clasificado por distancia y baudrate → `generate_csv.py`

Para ver la guía detallada de los pasos 1 y 2, consulte:
*   [Guía del Flujo de Trabajo Integrado con Ráfagas (workflow_bursts.md)](./workflow_bursts.md)
*   [Documentación Técnica del Segmentador (README_generate_bursts.md)](./README_generate_bursts.md)

### 1. Segmentar Ráfagas
Para segmentar automáticamente un directorio de audios continuos y guardarlos en una carpeta de salida:
```bash
python3 processing/generate_bursts.py data/<dataset>/ -o data_generated/<dataset>/ --grid
```

### 2. Demodular con run_suite.py
Para ejecutar la suite sobre el directorio de ráfagas generadas, ejecute desde el directorio raíz del repositorio y **guarde la salida en un archivo de texto** para el paso siguiente:
```bash
python3 processing/run_suite.py data_generated/<dataset>/ > salida.txt
```

### Gráficos de Salida (en carpeta `reportes/`):
*   `perfil_error_temporal_[alias].png`: Muestra de forma espacial la ubicación exacta de los bits recibidos correctamente (en verde) y los bits erróneos (en rojo) a lo largo de los miles de bits de la ráfaga, permitiendo diagnosticar la dinámica del transitorio de enganche y del canal.

---

## 📊 Generación del CSV de Resultados (`generate_csv.py`)

El script `generate_csv.py` toma la salida de texto de `run_suite.py` y los archivos de telemetría GPS de los bursts para generar un CSV con el BER clasificado por **distancia real** (calculada por GPS) y **baudrate**.

### Lógica de distancias

El script determina la distancia de cada sesión de medición de forma automática:
1. Lee las coordenadas GPS (lat/lon WGS-84) de los archivos `_burst_*.csv` del directorio
2. Ordena cronológicamente por timestamp GPS → el primer burst es el **punto de referencia (0 m)**
3. Calcula la distancia haversine de cada burst respecto al punto de referencia
4. Agrupa los bursts en sesiones usando un salto de distancia como separador (configurable o automático)

### Cálculo de BER

Las ráfagas del mismo baudrate dentro de una sesión se **acumulan** (no promedian), ya que la división en bursts existe únicamente por protección térmica del transmisor:

```
BER (%) = ( Σ errores de todas las ráfagas de la sesión/baudrate )
          ──────────────────────────────────────────────────────── × 100
          ( Σ bits   de todas las ráfagas de la sesión/baudrate )
```

### Uso

```bash
# Forma básica (umbral de sesión automático)
python3 processing/generate_csv.py -i salida.txt -d data_generated/<dataset>/ -o resultado.csv

# Con umbral de sesión explícito (en metros)
python3 processing/generate_csv.py -i salida.txt -d data_generated/<dataset>/ -o resultado.csv -t 200
```

| Argumento | Descripción | Requerido |
|-----------|-------------|-----------|
| `-i` / `--input`     | Archivo de texto con la salida de `run_suite.py` | ✅ |
| `-d` / `--dir`       | Directorio con los `_burst_*.csv` de GPS          | ✅ |
| `-o` / `--output`    | Archivo CSV de salida                             | ✅ |
| `-t` / `--threshold` | Umbral en metros para detectar cambio de sesión   | Opcional |

> Si `-t` se omite, el umbral se calcula automáticamente como `media + 2σ` de los saltos de distancia consecutivos.

### Formato del CSV de salida

```
Distancia_m,10,50,150,300,600,1200
0,0.00,0.00,0.36,0.03,0.06,5.39
552,0.00,0.08,0.05,0.04,0.06,5.80
...
```
