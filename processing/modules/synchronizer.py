"""
sincronizador.py — Sincronizador de Símbolo por Lazo de Seguimiento de Fase (DPLL)
============================================================================
Proyecto : Comunicación Digital sobre Radios Analógicas FM (JAR 2026)
Instituto: Instituto de Automática (INAUT) — UNSJ — CONICET

Implementa el lazo DPLL de segundo orden para sincronizar los instantes de
muestreo óptimo en el centro del bit (máxima apertura de ojo) y realizar un
seguimiento dinámico de la deriva de reloj y fase.
============================================================================
"""

import numpy as np
import config


class SincronizadorDPLL:
    """
    Sincronizador de Símbolo basado en un lazo de fase digital (DPLL) con filtro PI.
    """

    def __init__(self, fs=None, baud_rate=1200):
        self.fs = fs if fs is not None else config.FS_RX
        self.baud_rate = baud_rate
        
        # Período de símbolo nominal en muestras
        self.N_s = self.fs / self.baud_rate  # 19200 / 1200 = 16.0 muestras
        
        # Parámetros del controlador PI del lazo
        self.Kp = config.DPLL_KP
        self.Ki = config.DPLL_KI
        self.limite_integral = config.DPLL_LIMITE_INTEGRAL

        if config.MODO_VERBOSE:
            print(f"[SincronizadorDPLL] Inicializado: Ts={self.N_s:.2f} muestras.")
            print(f"  Ganancias del Lazo: Kp={self.Kp:.4f}, Ki={self.Ki:.5f}")

    def sincronizar(self, baseband_signal):
        """
        Ejecuta el lazo cerrado DPLL sobre la señal demodulada en banda base
        para localizar los índices óptimos de muestreo (strobes).

        Args:
            baseband_signal (np.ndarray): Señal de banda base demodulada (por ejemplo,
                                         la diferencia de energía o salida del discriminador).

        Returns:
            tuple: (indices_muestreo, fases_nco, errores_fase)
        """
        N = len(baseband_signal)
        
        # Inicializar variables del NCO (Oscilador Controlado Numéricamente)
        fase_nco = 0.0
        step_nominal = 1.0 / self.N_s  # 1 / 16 = 0.0625
        step = step_nominal
        integrador = 0.0
        
        indices_muestreo = []
        historial_fases = np.zeros(N)
        historial_errores = np.zeros(N)
        
        # Lazo DPLL a nivel de muestra
        for n in range(1, N):
            fase_prev = fase_nco
            fase_nco += step
            
            # 1. Detección de Transición (Cruce por cero del baseband)
            # Ocurre un cruce por cero si la señal cambia de signo entre n-1 y n
            cruce = (baseband_signal[n-1] * baseband_signal[n] < 0)
            
            error_fase = 0.0
            if cruce:
                # El cruce por cero (límite de símbolo) idealmente debería ocurrir
                # cuando la fase del NCO es exactamente 0.0 (o 1.0 en la envoltura circular).
                # Calculamos la desviación respecto a la referencia (0.0):
                if fase_nco > 0.5:
                    error_fase = fase_nco - 1.0
                else:
                    error_fase = fase_nco
                    
                # 2. Filtro de Lazo PI
                integrador += self.Ki * error_fase
                # Anti-windup (Saturación del integrador)
                integrador = np.clip(integrador, -self.limite_integral * step_nominal, self.limite_integral * step_nominal)
                
                # Ajuste de la frecuencia del NCO
                step = step_nominal + self.Kp * error_fase + integrador
                # Limitar paso para evitar desenganche catastrófico
                step = np.clip(step, 0.5 * step_nominal, 1.5 * step_nominal)
                
            # 3. Muestreo Óptimo (Strobe en fase = 0.5, centro del símbolo)
            # Ocurre cuando la fase del NCO cruza el umbral medio de 0.5
            if (fase_prev < 0.5 and fase_nco >= 0.5) or (fase_prev >= 0.5 and (fase_nco - 1.0) >= 0.5):
                indices_muestreo.append(n)
                
            # Envoltura circular del acumulador de fase
            if fase_nco >= 1.0:
                fase_nco -= 1.0
                
            historial_fases[n] = fase_nco
            historial_errores[n] = error_fase
            
        return np.array(indices_muestreo, dtype=int), historial_fases, historial_errores
