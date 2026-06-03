# 🧮 Referencia de Procesamiento en MATLAB

Este directorio contiene el script histórico de referencia desarrollado en MATLAB para simular y validar el algoritmo de demodulación Goertzel antes de su portabilidad a Python y MicroPython.

---

## 📂 Contenido

*   **`goertzel_go.m`**: Script principal de MATLAB que carga una señal grabada en formato `.wav`, aplica el preprocesamiento y ejecuta recursivamente las ecuaciones del filtro de respuesta al impulso infinita de Goertzel para calcular las envolventes espectrales de Mark y Space.

---

## ⚙️ Notas de Uso

*   **Entrada de Datos**: El script espera cargar archivos de audio `.wav` digitalizados a la frecuencia de muestreo unificada de la radio.
*   **Parámetros de Simulación**:
    *   Frecuencias nominales de tonos: $f_1 = 1200\text{ Hz}$ y $f_0 = 2400\text{ Hz}$.
    *   Tasa de muestreo nominal: $f_s = 19200\text{ Hz}$ (o $8000\text{ Hz}$ en las primeras campañas de ensayo analizadas en la subcarpeta `matlab` de desarrollo).
*   **Valor Científico**: Este script sirvió para contrastar la exactitud del cálculo de energía cuadrática de Goertzel frente a la transformada rápida de Fourier discreta, demostrando una reducción del costo computacional en el procesador, lo que habilitará su integración en tiempo real a bordo de la Raspberry Pi Pico.
