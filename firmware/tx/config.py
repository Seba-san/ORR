"""
config.py — Parámetros Centralizados del Sistema Transmisor AFSK
============================================================================
Proyecto : Comunicación Digital sobre Radios Analógicas FM (JAR 2026)
Instituto: Instituto de Automática (INAUT) — UNSJ — CONICET
Hardware : Raspberry Pi Pico 2W (RP2350) + Baofeng UV-82

Este módulo contiene todos los parámetros de configuración del sistema,
adaptados rigurosamente de la "Metodología Experimental" (metodologia_experimental.md).
============================================================================
"""

# ============================================================================
#  CONTROL DE DEPURACIÓN (DIAGNÓSTICO EN PC/THONNY)
# ============================================================================
DEBUG = True  # True para ver reportes en Thonny, False para optimización en campo

# ============================================================================
#  PARÁMETROS DE MODULACIÓN AFSK
# ============================================================================

# Frecuencias de tono AFSK (Hz) - Propuesta A (Ortogonal y Fase Sincrónica)
# Mark (bit lógico 1) y Space (bit lógico 0)
F_MARK  = 1200   # Hz — Tono para bit '1' (Exactamente 1.0 ciclo entero a 1200 bd)
F_SPACE = 2400   # Hz — Tono para bit '0' (Exactamente 2.0 ciclos enteros a 1200 bd)

# Velocidades de transmisión a ensayar (baudios)
# Cada pulsación del gatillo iniciará la transmisión en la siguiente velocidad,
# rotando de forma cíclica: 10 -> 50 -> 150 -> 300 -> 600 -> 1200
BAUD_RATES = [10, 50, 150, 300, 600, 1200]

# Frecuencia de muestreo del sintetizador de audio (Hz)
# Elevado a 19200 Hz para duplicar la resolución de la forma de onda
# y desplazar las espurias de muestreo digital fuera de la banda de audio.
# Divide de manera exacta a todas las velocidades de prueba:
#   19200 / 10   = 1920 muestras/bit
#   19200 / 50   = 384 muestras/bit
#   19200 / 150  = 128 muestras/bit
#   19200 / 300  = 64 muestras/bit
#   19200 / 600  = 32 muestras/bit
#   19200 / 1200 = 16 muestras/bit
FS = 19200  # Hz

# Frecuencia de la portadora PWM de hardware (Hz)
# Se utiliza 125 kHz para que la componente de conmutación esté muy alejada de la
# banda de voz. El atenuador resistivo de TX (10 kΩ serie + 1 kΩ shunt) reduce la
# señal de 3.3Vp-p a ~300mVp-p, y el capacitor de 47 µF acopla en serie la señal
# de audio bloqueando la continua, delegando el filtrado del portador PWM al ancho
# de banda extremadamente acotado del propio preamplificador de micrófono de la radio.
F_PWM = 125_000  # Hz

# Tamaño de la tabla de onda senoidal para síntesis digital directa (DDS)
TABLE_SIZE = 256

# ============================================================================
#  MAPEO DE PINES DE HARDWARE (RP2350)
# ============================================================================
PIN_PWM_TX  = 17     # GP17 (Pin físico 22) — Salida de audio PWM
PIN_PTT     = 16     # GP16 (Pin físico 21) — Control PTT (Optoacoplador PC817)
PIN_TRIGGER = 2      # GP2  (Pin físico 4)  — Pulsador de gatillo (con pull-up activa)
PIN_LED     = "LED"  # LED integrado para retroalimentación visual

# ============================================================================
#  TEMPORIZACIÓN Y CONFIGURACIÓN DE PTT
# ============================================================================
PTT_PRE_DELAY_MS  = 1000   # Retardo para apertura de squelch en receptor (ms)
PTT_POST_DELAY_MS = 1000  # Retardo de cola para propagación completa de muestras (ms)

# Habilita el modo de ensayo autónomo de campo (manos libres).
# - True: Cuenta regresiva de 10 min, tonos cada minuto, transmisión y avance de velocidades automático.
# - False: Sin espera, sin tonos, y cada velocidad requiere presionar GP2 manualmente (modo laboratorio/depuración).
AUTONOMOUS_MODE = True

# Tiempo de espera autónomo antes de la transmisión (minutos)
# Permite al operador caminar hasta su destino antes de iniciar la modulación de la trama.
# Cada minuto se enviará un tono/anuncio de 3s para retroalimentación en campo.
PRE_WAIT_MINUTES = 3



# ============================================================================
#  PROTECCIÓN TÉRMICA DE LA PORTADORA (Baofeng UV-82) Y GESTIÓN DE FRAGMENTACIÓN
# ============================================================================

# Volumen de datos total requerido por punto de ensayo para consistencia estadística
# Volumen de datos total requerido por punto de ensayo para consistencia estadística
# Nota: Modificado para velocidades lentas (50 bd y 150 bd) para evitar cuellos de botella térmicos
TOTAL_TEST_BITS = 12700  # 100 ciclos completos de la PRBS-7 (127 bits) de referencia

# Límite máximo de transmisión continua por ráfaga (segundos) - Optimización Térmica y de Batería
MAX_TX_TIME_S = 30  # Límite estricto de 30 segundos por ráfaga para proteger el PA de la radio

# Relación de ciclo de trabajo (Duty Cycle)
# Para un ciclo de trabajo máximo de 50% a Low Power (1W), se requiere que por cada
# segundo de transmisión activa (incluyendo pre y post delay), el equipo repose al menos 1 segundo.
COOLDOWN_RATIO = 1.0  # t_cooldown = COOLDOWN_RATIO * t_tx_actual

# Cooldown mínimo absoluto de seguridad (ms)
COOLDOWN_MIN_MS = 100

# Estructura de fragmentación detallada por velocidad según metodologia_experimental.md
# Asegura que ninguna transmisión individual supere los 30 segundos de duración
# y define las pausas mínimas obligatorias para mantener un ciclo de trabajo del 50%.
FRAGMENTATION = {
     10: {
        "burst_bits": 127,      # 10 ciclos de PRBS-7 (25.4 s de transmisión)
        "bursts": 1,             # 2 ráfagas completan 20 ciclos de PRBS-7 (2540 bits)
        "min_cooldown_s": 30     # Cooldown de 50% de Duty Cycle (PTT activo ~26.9s)
    },
    50: {
        "burst_bits": 1270,      # 10 ciclos de PRBS-7 (25.4 s de transmisión)
        "bursts": 2,             # 2 ráfagas completan 20 ciclos de PRBS-7 (2540 bits)
        "min_cooldown_s": 27     # Cooldown de 50% de Duty Cycle (PTT activo ~26.9s)
    },
    150: {
        "burst_bits": 3175,      # 25 ciclos de PRBS-7 (21.17 s de transmisión)
        "bursts": 2,             # 2 ráfagas completan 50 ciclos de PRBS-7 (6350 bits)
        "min_cooldown_s": 23     # Cooldown de 50% de Duty Cycle (PTT activo ~22.67s)
    },
    300: {
        "burst_bits": 6350,      # 50 ciclos de PRBS-7 (21.17 s de transmisión)
        "bursts": 2,             # 2 ráfagas completan 100 ciclos de PRBS-7 (12700 bits)
        "min_cooldown_s": 23     # Cooldown de 50% de Duty Cycle (PTT activo ~22.67s)
    },
    600: {
        "burst_bits": 12700,     # Ráfaga única de 100 ciclos de PRBS-7 (21.17 s de transmisión)
        "bursts": 1,
        "min_cooldown_s": 23     # Cooldown de 50% de Duty Cycle (PTT activo ~22.67s)
    },
    1200: {
        "burst_bits": 12700,     # Ráfaga única de 100 ciclos de PRBS-7 (10.58 s de transmisión)
        "bursts": 1,
        "min_cooldown_s": 12     # Cooldown de 50% de Duty Cycle (PTT activo ~12.08s)
    }
}

# ============================================================================
#  ANTIRREBOTE Y CONTROL DE GATILLO
# ============================================================================
TRIGGER_LOCKOUT_MS = 2000  # Tiempo de inmunidad a rebotes post-gatillado (ms)
