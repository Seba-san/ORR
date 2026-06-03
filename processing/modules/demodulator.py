"""
nucleo_demodulador.py — Núcleo de Demodulación AFSK por Algoritmo de Goertzel
============================================================================
Proyecto : Comunicación Digital sobre Radios Analógicas FM (JAR 2026)
Instituto: Instituto de Automática (INAUT) — UNSJ — CONICET

Implementa el procesamiento digital de señales para extraer la energía de los
tonos de Mark y Space a partir de muestras de audio preprocesadas.
Utiliza el algoritmo de Goertzel sintonizado de forma dinámica a las frecuencias
reales estimadas del transmisor.
============================================================================
"""

import numpy as np
import config


class DemoduladorAFSK:
    """
    Núcleo demodulador AFSK basado en el algoritmo de Goertzel sintonizado.
    """

    def __init__(self, f_mark=None, f_space=None, baud_rate=1200):
        self.fs = config.FS_RX
        self.baud_rate = baud_rate
        
        # Tamaño de la ventana de Goertzel en muestras (1 símbolo a 1200 baudios)
        self.N = self.fs // self.baud_rate  # 19200 // 1200 = 16 muestras
        
        # Usar frecuencias reales estimadas si están disponibles, o nominales en fallback
        self.f_mark = f_mark if f_mark is not None else config.F_MARK_NOMINAL
        self.f_space = f_space if f_space is not None else config.F_SPACE_NOMINAL

        # Precalcular coeficientes del filtro de Goertzel
        self.coeff_mark = self._calcular_coeficiente(self.f_mark)
        self.coeff_space = self._calcular_coeficiente(self.f_space)

        if config.MODO_VERBOSE:
            print(f"[DemoduladorAFSK] Inicializado: N={self.N} muestras por símbolo.")
            print(f"  MARK  sintonizado a: {self.f_mark:.1f} Hz (Coeff={self.coeff_mark:.4f})")
            print(f"  SPACE sintonizado a: {self.f_space:.1f} Hz (Coeff={self.coeff_space:.4f})")

    def _calcular_coeficiente(self, f_target):
        """
        Calcula el coeficiente de retroalimentación de Goertzel para una frecuencia dada.
        """
        # Frecuencia normalizada en radianes
        omega = 2.0 * np.pi * f_target / self.fs
        return 2.0 * np.cos(omega)

    def calcular_energia_tono(self, muestras, coeff):
        """
        Calcula la energía espectral de una frecuencia específica en un bloque de muestras
        utilizando la estructura recursiva de IIR del algoritmo de Goertzel.
        """
        # Variables de estado recursivas (Zero-Allocation)
        s0 = 0.0
        s1 = 0.0
        s2 = 0.0
        
        # Bucle recursivo directo
        for x in muestras:
            s0 = x + coeff * s1 - s2
            s2 = s1
            s1 = s0
            
        # Calcular magnitud cuadrada final
        potencia = s1**2 + s2**2 - coeff * s1 * s2
        return potencia

    def procesar_simbolo(self, muestras):
        """
        Procesa un bloque de N muestras (1 símbolo) y decide el bit correspondiente.

        Args:
            muestras (np.ndarray): Bloque de N muestras centrado en el símbolo.

        Returns:
            tuple: (bit_decidido, confianza_Ck, E_mark, E_space)
        """
        # Calcular energías locales de cada tono
        E_mark = self.calcular_energia_tono(muestras, self.coeff_mark)
        E_space = self.calcular_energia_tono(muestras, self.coeff_space)

        # Decisión de bit
        # MARK (1200 Hz) = bit '1', SPACE (2400 Hz) = bit '0'
        if E_mark > E_space:
            bit = 1
        else:
            bit = 0

        # Calcular factor de confianza Ck normalizado [0.0, 1.0]
        # Agrega un pequeño epsilon en el denominador para evitar división por cero
        epsilon = 1e-9
        Ck = np.abs(E_mark - E_space) / (E_mark + E_space + epsilon)

        return bit, Ck, E_mark, E_space
