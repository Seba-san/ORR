"""
filtro_inicial.py — Filtro FIR Pasa-Banda de Preprocesamiento
============================================================================
Proyecto : Comunicación Digital sobre Radios Analógicas FM (JAR 2026)
Instituto: Instituto de Automática (INAUT) — UNSJ — CONICET

Implementa el primer eslabón de la cadena de demodulación: un filtro
pasa-banda FIR de alto orden diseñado con ventana Kaiser. Su objetivo
es eliminar toda energía fuera de la banda acústica de interés (300-3000 Hz),
reduciendo la contaminación espectral por ruido del canal FM, zumbidos de
red eléctrica (50/60 Hz) y armónicos de alta frecuencia del transmisor PWM,
antes de que la señal llegue al analizador espectral y al Goertzel.

Uso:
    from filtro_inicial import FiltroFIR
    filtro = FiltroFIR()
    señal_filtrada = filtro.aplicar(señal_cruda)
    filtro.imprimir_reporte()
============================================================================
"""

import numpy as np
from scipy.signal import firwin, freqz, lfilter
import config


class FiltroFIR:
    """
    Filtro pasa-banda FIR de alto orden con ventana Kaiser.

    El diseño de punto fijo (coeficientes calculados una sola vez en
    __init__) garantiza que el costo computacional en el lazo de
    demodulación sea mínimo: solo una convolución por bloque de audio.
    """

    def __init__(self):
        """
        Calcula los coeficientes del filtro FIR al instanciar el objeto.
        Los parámetros se leen desde config.py para mantener consistencia
        centralizada en todo el sistema.
        """
        self.orden     = config.FIR_ORDEN
        self.frec_baja = config.FIR_FREC_BAJA_HZ
        self.frec_alta = config.FIR_FREC_ALTA_HZ
        self.beta      = config.FIR_BETA_KAISER
        self.fs        = config.FS_RX

        # Frecuencias normalizadas (Nyquist = 1.0)
        nyquist = self.fs / 2.0
        frec_baja_norm = self.frec_baja / nyquist
        frec_alta_norm = self.frec_alta / nyquist

        # Diseño del filtro pasa-banda con firwin (ventana Kaiser)
        # firwin con dos frecuencias de corte y pass_zero=False → pasa-banda
        self.coeficientes = firwin(
            numtaps=self.orden + 1,        # Número de taps = orden + 1
            cutoff=[frec_baja_norm, frec_alta_norm],
            window=('kaiser', self.beta),
            pass_zero=False                # False = modo pasa-banda
        )

        if config.MODO_VERBOSE:
            print(f"[FiltroFIR] Filtro diseñado: orden={self.orden}, "
                  f"banda={self.frec_baja}-{self.frec_alta} Hz, "
                  f"Beta Kaiser={self.beta}")

    def aplicar(self, señal: np.ndarray) -> np.ndarray:
        """
        Aplica el filtro FIR a una señal de entrada mediante convolución lineal.

        Se usa lfilter (causal, un solo paso hacia adelante) en lugar de
        filtfilt para respetar la causalidad del sistema — condición necesaria
        para el posterior sincronizador de símbolo DPLL.

        Args:
            señal (np.ndarray): Señal de entrada en formato float64, normalizada
                                al rango [-1.0, +1.0].

        Returns:
            np.ndarray: Señal filtrada, mismo largo que la entrada. Los primeros
                        `orden/2` muestras tendrán artefactos de inicio (transitorio
                        del filtro), que son inherentes a los filtros FIR causales.
        """
        if señal.dtype != np.float64:
            señal = señal.astype(np.float64)

        return lfilter(self.coeficientes, 1.0, señal)

    def respuesta_en_frecuencia(self, n_puntos: int = 4096):
        """
        Calcula la respuesta en frecuencia del filtro para verificación.

        Args:
            n_puntos (int): Número de puntos de evaluación de la respuesta.

        Returns:
            tuple[np.ndarray, np.ndarray]: (frecuencias_hz, magnitud_db)
        """
        frecuencias_norm, H = freqz(self.coeficientes, worN=n_puntos, fs=self.fs)
        magnitud_db = 20 * np.log10(np.abs(H) + 1e-12)
        return frecuencias_norm, magnitud_db

    def imprimir_reporte(self):
        """
        Imprime en consola un resumen de las características del filtro,
        incluyendo la atenuación real en frecuencias clave.
        """
        freqs, mag_db = self.respuesta_en_frecuencia()

        def atenuacion_en(f_hz):
            idx = np.argmin(np.abs(freqs - f_hz))
            return mag_db[idx]

        print("\n[FiltroFIR] === Reporte de Diseño ===")
        print(f"  Tipo          : FIR Pasa-Banda (ventana Kaiser)")
        print(f"  Orden         : {self.orden} taps={self.orden + 1}")
        print(f"  Banda de paso : {self.frec_baja} Hz — {self.frec_alta} Hz")
        print(f"  Beta Kaiser   : {self.beta} (~{self.beta * 8:.0f} dB de atenuación en lóbulos)")
        print(f"  Fs            : {self.fs} Hz")
        print(f"  Atenuación en frecuencias clave:")
        for f in [10, 50, 100, 300, 500, 1200, 1800, 2400, 3000, 3500, 4000]:
            if f <= self.fs / 2:
                print(f"    {f:5d} Hz → {atenuacion_en(f):+7.1f} dB")
        print()
