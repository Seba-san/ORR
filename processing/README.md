# 📊 Suite de Procesamiento y Demodulación *Offline*

Esta carpeta contiene la suite de herramientas desarrolladas en **Python** para la demodulación síncrona *offline* y la caracterización espectral de las señales de audio AFSK capturadas por el Web-DAQ.

---

## 🚀 Flujo del Procesamiento Digital de Señales (DSP)

El software realiza el procesamiento en seis etapas secuenciales de bajo nivel:

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
                                    ▼
                  +-----------------------------------+
                  |   Filtros de Banda Adaptativos    |
                  +-----------------------------------+
                                    │
                                    ▼
                  +-----------------------------------+
                  | Detección y Balance de Envolvente |
                  +-----------------------------------+
                                    │
                                    ▼
                  +-----------------------------------+
                  | Búsqueda de Fase y Decisión de Bit|
                  +-----------------------------------+
                                    │
                                    ▼
                  +-----------------------------------+
                  |    Cálculo de BER y Confianza     |
                  +-----------------------------------+
```

1.  **Acondicionamiento (Filtro FIR Kaiser):** Un filtro de respuesta al impulso finita (FIR) de fase lineal de orden 127 aísla la banda útil (300 Hz a 3000 Hz), eliminando ruidos fuera de banda tales como zumbidos de red de 50/60 Hz.
2.  **Autocalibración Espectral (Transformada Rápida de Fourier):** Ejecuta una transformada rápida de Fourier para detectar las frecuencias reales del transmisor (Mark y Space), compensando corrimientos locales debidos a derivas térmicas de los osciladores.
3.  **Filtros de Banda Adaptativos:** Aplica filtros pasa-banda Butterworth de segundo orden con ancho de banda adaptado al *baudrate* de transmisión para separar las componentes de Mark y Space minimizando la interferencia intersimbólica (ISI).
4.  **Detección y Balance de Envolvente:** Estima las envolventes de amplitud mediante el valor absoluto de las señales de salida filtradas y un filtro pasa-bajos Butterworth de segundo orden. A partir de los percentiles de amplitud en el segmento activo, calcula y aplica un factor de ganancia de balance $g$ para restar la atenuación de alta frecuencia en la línea: $y_{\text{balanceada}} = env_{\text{mark}} - g \cdot env_{\text{space}}$.
5.  **Búsqueda de Fase y Decisión de Bit:** Realiza una búsqueda en rejilla (*Grid Search*) de la fase temporal inicial de la ráfaga de datos para alinear el instante de muestreo del primer bit minimizando la tasa de error de bit (BER), evaluando luego la secuencia a intervalos constantes.
6.  **Evaluación de BER:** Alinea la secuencia demodulada mediante correlación cruzada contra el patrón local PRBS-7 de 127 bits de Golomb ($y(n) = y(n-6) \oplus y(n-7)$) y calcula la Tasa de Error de Bit (BER) sobre la ráfaga completa.

---

## 🛠️ Instalación de Dependencias

Se requiere tener instalado **Python 3.10+** en el sistema. Para instalar los requisitos matemáticos necesarios, ejecuta:

```bash
pip install -r requirements.txt
```

---

## ⚡ Ejecución de la Demodulación y Segmentación

Para procesar de forma correcta los datasets que contienen múltiples transmisiones continuas con silencios y ruido FM intermedio, el flujo recomendado consiste en:
1. **Segmentar automáticamente** los audios continuos en ráfagas individuales usando `generate_bursts.py`.
2. **Ejecutar la suite de demodulación** `run_suite.py` sobre los audios resultantes.

Para ver una explicación detallada del flujo completo paso a paso, consulte la guía:
*   [Guía del Flujo de Trabajo Integrado con Ráfagas (workflow_bursts.md)](./workflow_bursts.md)
*   [Documentación Técnica del Segmentador (README_generate_bursts.md)](./README_generate_bursts.md)

### 1. Segmentar Ráfagas
Para segmentar automáticamente un directorio de audios continuos y guardarlos en una carpeta de salida:
```bash
python3 processing/generate_bursts.py data/libre/5 -o data_generated/5 --grid
```

### 2. Procesar con run_suite.py
Para ejecutar la suite sobre el directorio de ráfagas generadas, ejecute desde el directorio raíz del repositorio:
```bash
python3 processing/run_suite.py data_generated/5
```

### Gráficos de Salida (en carpeta `reportes/`):
*   `perfil_error_temporal_[alias].png`: Muestra de forma espacial la ubicación exacta de los bits recibidos correctamente (en verde) y los bits erróneos (en rojo) a lo largo de los miles de bits de la ráfaga, permitiendo diagnosticar la dinámica del transitorio de enganche y del canal.
