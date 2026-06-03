# 📊 Suite de Procesamiento y Demodulación *Offline*

Esta carpeta contiene la suite de herramientas desarrolladas en **Python** para la demodulación síncrona *offline* y la caracterización espectral de las señales de audio AFSK capturadas por el Web-DAQ.

---

## 🚀 Flujo del Procesamiento Digital de Señales (DSP)

El software realiza el procesamiento en cinco etapas secuenciales de bajo nivel:

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
                  |  Analizador Fourier (Autotuning)   |
                  +-----------------------------------+
                                    │
                                    ▼
                  +-----------------------------------+
                  |    Banco de Filtros Goertzel      |
                  +-----------------------------------+
                                    │
                                    ▼
                  +-----------------------------------+
                  | Sincronismo DPLL + Decisión Bit   |
                  +-----------------------------------+
                                    │
                                    ▼
                  +-----------------------------------+
                  |   Cálculo de BER y Confianza      |
                  +-----------------------------------+
```

1.  **Acondicionamiento (Filtro FIR Kaiser):** Un filtro de respuesta al impulso finita (FIR) de fase lineal de orden 127 aísla la banda útil (300 Hz a 3000 Hz), barriendo ruidos fuera de banda como zumbidos de red de 50/60 Hz y clicks analógicos.
2.  **Autocalibración Espectral (Transformada Rápida de Fourier):** Ejecuta una transformada rápida de Fourier para detectar las frecuencias reales exactas de Mark y Space, compensando corrimientos locales debidos a la deriva térmica de los microcontroladores de campo.
3.  **Extracción de Energía (Algoritmo de Goertzel):** Aplica la estructura de filtro recursivo de respuesta al impulso infinita de segundo orden de Goertzel sintonizado exactamente a los picos reales detectados para estimar la potencia instantánea de cada tono en cada símbolo.
4.  **Sincronismo de Reloj y DPLL:** Un lazo de seguimiento de fase digital con un controlador proporcional-integral de segundo orden rastrea y compensa la deriva del reloj físico para realizar el muestreo en el instante de máxima apertura del ojo del bit.
5.  **Evaluación de BER:** Alinea la secuencia demodulada mediante correlación cruzada contra el patrón local PRBS-7 de 127 bits de Golomb ($y(n) = y(n-6) \oplus y(n-7)$) y computa la Tasa de Error de Bit (BER) exacta sobre toda la ráfaga.

---

## 🛠️ Instalación de Dependencias

Se requiere tener instalado **Python 3.10+** en el sistema. Para instalar los requisitos matemáticos necesarios, ejecuta:

```bash
pip install -r requirements.txt
```

---

## ⚡ Ejecución de la Demodulación

El script principal de integración y diagnóstico es `run_suite.py`. Al ejecutarlo, buscará los archivos WAV configurados en [modules/config.py](./modules/config.py), demodulará las señales y generará un reporte consolidado en la consola junto con gráficos detallados de error temporal y curvas en el directorio `reportes/`.

Para correr la demodulación sobre los archivos de prueba del proyecto:

```bash
python3 run_suite.py
```

### Gráficos de Salida (en carpeta `reportes/`):
*   `perfil_error_temporal_[alias].png`: Muestra de forma espacial la ubicación exacta de los bits recibidos correctamente (en verde) y los bits erróneos (en rojo) a lo largo de los miles de bits de la ráfaga, permitiendo diagnosticar la dinámica del transitorio de enganche y del canal.
