"""
config.py — Parámetros Centralizados del Demodulador Universal AFSK
============================================================================
Proyecto : Comunicación Digital sobre Radios Analógicas FM (JAR 2026)
Instituto: Instituto de Automática (INAUT) — UNSJ — CONICET

Módulo de configuración única y centralizada para el demodulador universal.
Todos los parámetros del sistema se definen aquí. Ningún otro módulo debe
contener constantes numéricas "mágicas"; siempre deben referenciar este archivo.

Modificar este archivo es la única acción necesaria para adaptar el sistema
a nuevas condiciones de canal, hardware o velocidades de prueba.
============================================================================
"""

import os

# ============================================================================
#  PARÁMETROS DE LA SEÑAL AFSK (Capa Física)
# ============================================================================

# Frecuencias nominales de los tonos AFSK (Hz)
# Mark = bit lógico '1', Space = bit lógico '0'
# Deben coincidir con lo configurado en tx_python/config.py del transmisor.
F_MARK_NOMINAL  = 1200   # Hz
F_SPACE_NOMINAL = 2400   # Hz

# Frecuencia de muestreo del receptor (Hz)
# Definida por rx_python/config.py: SAMPLE_RATE = 19200 Hz
FS_RX = 19200  # Hz

# Rango de búsqueda espectral para autocalibración de tonos (Hz)
# Define la ventana alrededor de cada frecuencia nominal donde
# el analizador espectral buscará el pico real.
RANGO_BUSQUEDA_MARK_HZ  = 150   # ± Hz alrededor de F_MARK_NOMINAL
RANGO_BUSQUEDA_SPACE_HZ = 150   # ± Hz alrededor de F_SPACE_NOMINAL

# ============================================================================
#  VELOCIDADES DE SÍMBOLO SOPORTADAS (Baud Rate)
# ============================================================================

# Lista ordenada de velocidades candidatas para la autodetección.
# El detector de baudios buscará la mejor coincidencia dentro de este conjunto.
BAUD_RATES_CANDIDATOS = [10, 50, 150, 300, 600, 1200]  # baudios

# ============================================================================
#  PARÁMETROS DEL FILTRO FIR DE PREPROCESAMIENTO
# ============================================================================

# Filtro pasa-banda FIR de alto orden (ventana Kaiser) para aislar la banda
# acústica AFSK y eliminar ruido fuera de banda (60 Hz de red, ruido RF, etc.)
FIR_ORDEN        = 127   # Orden del filtro (impar para simetría exacta)
FIR_FREC_BAJA_HZ = 300   # Frecuencia de corte inferior (Hz) — elimina zumbidos DC y 50/60 Hz
FIR_FREC_ALTA_HZ = 3000  # Frecuencia de corte superior (Hz) — elimina ruido de alta frecuencia
FIR_BETA_KAISER  = 8.6   # Parámetro Beta de la ventana Kaiser (compromiso lóbulo-atenuación)
                          # Beta=8.6 → atenuación de lóbulos laterales ≈ -60 dB

# ============================================================================
#  PARÁMETROS DEL ANALIZADOR ESPECTRAL (FFT DE VENTANA DESLIZANTE)
# ============================================================================

# Tamaño de la ventana FFT en muestras para el análisis espectral por ventana.
# Se asume 1200 bd como hipótesis inicial (caso más exigente en términos de
# resolución temporal), lo que corresponde a FS_RX / 1200 ≈ 6.67 muestras/símbolo.
# Para obtener buena resolución espectral, se usan múltiplos del período de símbolo.
# Con 512 muestras a 19200 Hz → resolución de 37.5 Hz (adecuada para separar 1200 y 2400 Hz).
FFT_VENTANA_MUESTRAS = 512   # muestras (potencia de 2 para eficiencia FFT)
FFT_SOLAPAMIENTO     = 0.75  # Fracción de solapamiento entre ventanas consecutivas (overlap)
                              # 0.75 → 75% de overlap → mayor resolución temporal

# Tipo de ventana de ponderación para la FFT (reduce las fugas espectrales)
# 'hann' es el equilibrio entre resolución y supresión de lóbulos laterales.
FFT_TIPO_VENTANA = 'hann'

# ============================================================================
#  PARÁMETROS DEL SINCRONIZADOR DE SÍMBOLO (DPLL)
# ============================================================================

# Ganancias del controlador Proporcional-Integral (PI) del lazo DPLL.
# Kp: respuesta rápida a errores de fase instantáneos.
# Ki: corrección acumulada de errores de fase sostenidos (deriva lenta de reloj).
# Valores iniciales conservadores; se ajustarán en el Hito 3 (HITL 3).
DPLL_KP = 0.05   # Ganancia proporcional (adimensional)
DPLL_KI = 0.001  # Ganancia integral (adimensional)

# Límite de saturación del integrador (anti-windup) en fracciones de período de símbolo
DPLL_LIMITE_INTEGRAL = 0.1  # ± 10% del período de símbolo

# ============================================================================
#  PARÁMETROS DEL ALGORITMO DE GOERTZEL
# ============================================================================

# El tamaño de la ventana de Goertzel define cuántas muestras se usan para
# calcular la energía de cada tono en un instante dado.
# Este valor se recalcula en tiempo de ejecución según el baud rate detectado:
#   N_goertzel = FS_RX // baud_rate  (una ventana = exactamente un período de símbolo)
# Este parámetro define el multiplicador de ventana (cuántos períodos promediar).
GOERTZEL_PERIODOS_POR_VENTANA = 1   # 1 = exactamente 1 símbolo por cálculo

# ============================================================================
#  PARÁMETROS DE LA SECUENCIA PRBS-7 (Patrón de Referencia)
# ============================================================================

# Semilla del LFSR para la generación de PRBS-7.
# Debe coincidir con la semilla usada en tx_python/lfsr.py del transmisor.
PRBS7_SEED           = 0x7F   # Todos los bits en 1 (estado inicial maximal)
PRBS7_LONGITUD_CICLO = 127    # Bits por ciclo completo (2^7 - 1)

# ============================================================================
#  UMBRALES DE DECISIÓN Y FACTOR DE CONFIANZA
# ============================================================================

# Umbral mínimo de confianza Ck para considerar un bit como "dato válido".
# Bits con Ck < UMBRAL_CONFIANZA_MINIMA se marcan como "baja confianza".
# Rango: [0.0 = máxima incertidumbre, 1.0 = certeza]
UMBRAL_CONFIANZA_MINIMA = 0.15  # Valor inicial conservador; ajustar en HITL 3

# Umbral de energía para detectar segmentos activos (con señal) vs. silencio.
# Se usa en la detección de actividad previa al análisis. Es relativo a la
# energía RMS del archivo completo.
UMBRAL_ACTIVIDAD_RMS = 0.10  # 10% del RMS máximo del archivo

# ============================================================================
#  CONFIGURACIÓN DE SALIDA Y REPORTES
# ============================================================================

# Directorio de salida para las imágenes generadas por el visualizador.
# Se crea automáticamente si no existe.
DIR_SALIDA_GRAFICOS = os.path.join(os.path.dirname(__file__), 'reportes')

# Activar impresión detallada en consola durante el procesamiento.
MODO_VERBOSE = False

# ============================================================================
#  CONFIGURACIONES DE FILTRADO Y DETECCIÓN (HITL 3)
# ============================================================================
FILTRO_BANDPASS_ORDEN    = 4     # Orden para filtros adaptativos de Mark/Space
FILTRO_LOWPASS_ENV_ORDEN = 4     # Orden para filtro pasa-bajos de envolvente
FILTRO_LOWPASS_ENV_FACTOR = 0.75 # Multiplicador del cutoff (factor * baud_rate)

# Umbral de energía para la detección de inicio de ráfaga
SQUELCH_FACTOR_INICIO    = 0.50  # Fracción de potencia máxima para inicio
TRANSITORIO_INICIO_S      = 0.15  # Tiempo a omitir para evitar clicks y transitorios (segundos)

# Ventana de guarda para el DPLL (para tolerancia de jitter)
DPLL_VENTANA_GUARDA      = 0.50  # Permitir corregir hasta medio símbolo de desfase

# Mapeo de bits esperados por velocidad
BITS_POR_VELOCIDAD = {
    10: 127,
    50: 1270,
    150: 3175,
    300: 6350,
    600: 12700,
    1200: 12700
}

# Candidatos para la grilla de búsqueda de ganancias DPLL (Grid Search)
DPLL_KP_CANDIDATOS = [0.01, 0.02, 0.05, 0.08, 0.12, 0.18, 0.25]
DPLL_KI_CANDIDATOS = [0.0001, 0.0005, 0.001, 0.002, 0.004, 0.008]


