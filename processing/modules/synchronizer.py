"""
sincronizador.py — Sincronizador de Símbolo por Lazo de Seguimiento de Fase (DPLL)
============================================================================
Proyecto : Comunicación Digital sobre Radios Analógicas FM (JAR 2026)
Instituto: Instituto de Automática (INAUT) — UNSJ — CONICET

Implementa el lazo DPLL de segundo orden para sincronizar los instantes de
muestreo en el centro del bit (máxima apertura de ojo) y realizar un
seguimiento dinámico de la deriva de reloj y fase.
============================================================================
"""

import numpy as np
import config


class SincronizadorDPLL:
    """
    Sincronizador de Símbolo basado en un lazo de fase digital (DPLL) con filtro PI.
    """

    def __init__(self, fs=None, baud_rate=1200, umbral_amplitud=0.15, ventana_guarda=0.25):
        self.fs = fs if fs is not None else config.FS_RX
        self.baud_rate = baud_rate
        self.umbral_amplitud = umbral_amplitud
        self.ventana_guarda = ventana_guarda
        
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
        para localizar los índices de muestreo (strobes).

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
        
        # Calcular el límite del squelch basado en el pico de amplitud
        limite_amplitud = self.umbral_amplitud * np.max(np.abs(baseband_signal))
        
        # Lazo DPLL a nivel de muestra
        for n in range(1, N):
            fase_prev = fase_nco
            fase_nco += step
            
            # 1. Detección de Transición (Cruce por cero)
            cruce = (baseband_signal[n-1] * baseband_signal[n] < 0)
            
            error_fase = 0.0
            if cruce:
                # Interpolación lineal para estimar el instante exacto del cruce por cero entre n-1 y n
                v_prev = baseband_signal[n-1]
                v_curr = baseband_signal[n]
                frac = -v_prev / (v_curr - v_prev + 1e-12)
                fase_cruce = fase_prev + frac * step
                if fase_cruce >= 1.0:
                    fase_cruce -= 1.0
                    
                # El cruce por cero idealmente debería ocurrir en fase = 0.0
                if fase_cruce > 0.5:
                    error_fase = fase_cruce - 1.0
                else:
                    error_fase = fase_cruce
                    
                # Filtro por Ventana de Guarda: ignorar si el error es aberrante (ruido)
                if np.abs(error_fase) > self.ventana_guarda:
                    error_fase = 0.0
                else:
                    # 2. Filtro de Lazo PI con realimentación negativa
                    integrador -= self.Ki * error_fase
                    # Anti-windup (Saturación del integrador)
                    integrador = np.clip(integrador, -self.limite_integral, self.limite_integral)
                    
                    # Ajuste de la frecuencia del NCO (realimentación negativa)
                    step = step_nominal * (1.0 - self.Kp * error_fase + integrador)
                    # Limitar paso para evitar desenganche catastrófico (±5% de la nominal)
                    step = np.clip(step, 0.95 * step_nominal, 1.05 * step_nominal)


                
            # 3. Instante de muestreo (Strobe en fase = 0.5, centro del símbolo)
            # Ocurre cuando la fase del NCO cruza el umbral medio de 0.5
            if (fase_prev < 0.5 and fase_nco >= 0.5) or (fase_prev >= 0.5 and (fase_nco - 1.0) >= 0.5):
                indices_muestreo.append(n)
                
            # Envoltura circular del acumulador de fase
            if fase_nco >= 1.0:
                fase_nco -= 1.0
                
            historial_fases[n] = fase_nco
            historial_errores[n] = error_fase
            
        return np.array(indices_muestreo, dtype=int), historial_fases, historial_errores
