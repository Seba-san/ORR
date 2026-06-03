"""
detector_baudios.py — Detección Automática de Velocidad de Transmisión (Baud Rate)
============================================================================
Proyecto : Comunicación Digital sobre Radios Analógicas FM (JAR 2026)
Instituto: Instituto de Automática (INAUT) — UNSJ — CONICET

Implementa el tercer eslabón de la cadena de demodulación: el algoritmo de
detección automática de Baud Rate. El sistema procesa la señal de audio
preprocesada, extrae la envolvente de transiciones y determina cuál es la
velocidad de símbolo en {10, 50, 150, 300, 600, 1200} baudios.

Estrategia (definida en HITL 0 y plan_de_implementacion):
  1. Filtrado pasa-banda IIR sintonizado de alta velocidad alrededor de las
     frecuencias reales estimadas para Mark y Space.
  2. Extracción de energía local y cálculo de la diferencia de envolventes:
     d(t) = E_mark(t) - E_space(t).
  3. Extracción de transiciones: r(t) = |d(t) - d(t-1)|. Esta señal presenta
     picos agudos en los instantes de cruce o cambio de símbolo.
  4. Autocorrelación de r(t) sobre el segmento activo. El primer pico
     prominente posterior a lag=0 indica la duración de símbolo Ts en muestras.
  5. Clasificación robusta de mínima distancia contra los baudios candidatos.
============================================================================
"""

import numpy as np
from scipy.signal import butter, lfilter
import config


class DetectorBaudios:
    """
    Detector automático de velocidad de transmisión (Baud Rate) para señales AFSK.

    Combina el análisis de transiciones de envolvente de potencia con la
    autocorrelación temporal de la derivada para determinar de manera robusta
    la tasa de símbolos (baudios) nominal del canal de audio FM.
    """

    def __init__(self):
        self.fs = config.FS_RX
        self.candidatos = config.BAUD_RATES_CANDIDATOS

        if config.MODO_VERBOSE:
            print(f"[DetectorBaudios] Inicializado. Candidatos: {self.candidatos} baudios")

    def _diseñar_iir_pasa_banda(self, f_centro: float, ancho_banda: float = 160.0) -> tuple:
        """
        Diseña un filtro pasa-banda Butterworth de 2do orden utilizando scipy.signal.butter.
        Altamente selectivo y computacionalmente liviano para estimar la envolvente local.
        """
        nyquist = self.fs / 2.0
        f_baja = max(100.0, f_centro - ancho_banda / 2.0)
        f_alta = min(nyquist - 100.0, f_centro + ancho_banda / 2.0)
        
        b, a = butter(2, [f_baja / nyquist, f_alta / nyquist], btype='bandpass')
        return b, a

    def detectar(self, señal_filtrada: np.ndarray, f_mark: float = None, f_space: float = None) -> float:
        """
        Analiza la señal filtrada de entrada y estima la velocidad nominal (Baud Rate).

        Utiliza un método robusto de producto de retardo en cuadratura (FM Discriminator)
        junto con un análisis estadístico de los intervalos entre cruces por cero
        para clasificar con precisión la tasa de símbolos en {10, 50, 150, 300, 600, 1200} bd.

        Args:
            señal_filtrada (np.ndarray): Señal de audio preprocesada por FiltroFIR.
            f_mark (float, opcional): Frecuencia real estimada del tono Mark.
            f_space (float, opcional): Frecuencia real estimada del tono Space.

        Returns:
            float: Baud rate detectado (de entre los candidatos en config.py).
        """
        # 1. Demodulación analítica rápida por producto de retardo en cuadratura (FM Discriminator)
        # Un retardo tau=2 muestras a 19200 Hz es óptimo para discriminar entre 1200 y 2400 Hz
        tau = 2
        y = señal_filtrada[tau:] * señal_filtrada[:-tau]
        y = np.insert(y, 0, [0.0]*tau)

        # 2. Filtrado Pasa-Bajos a 1200 Hz para eliminar armónicos de portadora y rizados residuales
        nyquist = self.fs / 2.0
        b_lp, a_lp = butter(2, 1200.0 / nyquist, btype='low')
        y_lp = lfilter(b_lp, a_lp, y)

        # Centrar la señal respecto a su valor medio local
        y_centrada = y_lp - np.mean(y_lp)

        # 3. Aislamiento del segmento activo de señal (ignorar silencios iniciales/finales de PTT)
        n_rms = int(0.05 * self.fs)
        rms_local = np.sqrt(np.convolve(y_centrada**2, np.ones(n_rms)/n_rms, mode='same'))
        
        # Umbral adaptativo del 15% de la energía RMS máxima
        umbral = 0.15 * np.max(rms_local)
        indices_activos = np.where(rms_local > umbral)[0]

        if len(indices_activos) > self.fs * 0.1: # Al menos 100 ms activos
            y_activa = y_centrada[indices_activos[0] : indices_activos[-1]]
        else:
            y_activa = y_centrada

        # 4. Localizar los instantes de cruce por cero (zero-crossing)
        zero_crossings = np.where(y_activa[:-1] * y_activa[1:] < 0)[0]

        # 5. Calcular intervalos temporales entre transiciones
        intervals = np.diff(zero_crossings)

        # Filtrar espurios o ruidos no físicos excesivamente cortos (menores a 8 muestras ~2400 bd)
        # Esto blinda el estimador frente a variaciones rápidas de ruido en canales degradados
        intervals = intervals[intervals >= 8]

        # Fallback si no hay suficientes transiciones registradas
        if len(intervals) < 3:
            baud_detectado = 1200
            if config.MODO_VERBOSE:
                print(f"[DetectorBaudios] ⚠️ Insuficientes transiciones ({len(zero_crossings)}). Fallback a 1200 bd.")
            return baud_detectado

        # 6. Puntuación por mínimos errores de ajuste contra múltiplos de símbolo
        scores = []
        for cand in self.candidatos:
            N_s = self.fs / cand  # Duración del símbolo en muestras para este candidato
            errores = []
            for val in intervals:
                # Determinar cuántos símbolos enteros representa este intervalo
                k = round(val / N_s)
                if k == 0:
                    k = 1
                # Error relativo normalizado respecto a la duración teórica del símbolo
                err = np.abs(val - k * N_s) / N_s
                errores.append(err)
            scores.append(np.mean(errores))

        # Seleccionar el candidato con el menor error de ajuste estadístico
        idx_candidato = np.argmin(scores)
        baud_detectado = self.candidatos[idx_candidato]

        if config.MODO_VERBOSE:
            print(f"[DetectorBaudios] Cruces por cero analizados: {len(zero_crossings)} | Intervalos válidos: {len(intervals)}")
            print(f"[DetectorBaudios] Clasificado a candidato más cercano: {baud_detectado} bd (Error medio: {scores[idx_candidato]:.4f})")

        return baud_detectado
