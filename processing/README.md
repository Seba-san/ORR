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

## ⚡ Ejecución de la Demodulación

El script principal de integración y diagnóstico es `run_suite.py`. Admite como argumento opcional la ruta de la carpeta que contiene los archivos de audio .wav (si no se proporciona, buscará en `./audio`, `./audios` o en el directorio actual). El script realiza de forma automática la estimación de la velocidad de transmisión de cada audio a través de pruebas de demodulación y reporta las métricas de canal correspondientes.

Para ejecutar el procesamiento, ejecute desde el directorio raíz del repositorio:

```bash
python3 processing/run_suite.py [ruta_al_directorio_de_audios]
```

Por ejemplo:

```bash
python3 processing/run_suite.py audio
```

### Gráficos de Salida (en carpeta `reportes/`):
*   `perfil_error_temporal_[alias].png`: Muestra de forma espacial la ubicación exacta de los bits recibidos correctamente (en verde) y los bits erróneos (en rojo) a lo largo de los miles de bits de la ráfaga, permitiendo diagnosticar la dinámica del transitorio de enganche y del canal.
