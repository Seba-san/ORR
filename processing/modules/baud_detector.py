"""
detector_baudios.py — Detección Automática de Velocidad de Transmisión (Baud Rate)
============================================================================
Proyecto : Comunicación Digital sobre Radios Analógicas FM (JAR 2026)
Instituto: Instituto de Automática (INAUT) — UNSJ — CONICET

Implementa el tercer eslabón de la cadena de demodulación: el algoritmo de
detección automática de Baud Rate. El sistema procesa la señal de audio
preprocesada, realiza pruebas de demodulación para cada una de las velocidades
candidatas y determina cuál de ellas minimiza la tasa de error de bit.
============================================================================
"""

import numpy as np
import config


class DetectorBaudios:
    """
    Detector automático de velocidad de transmisión (Baud Rate) para señales AFSK.

    Estima la velocidad nominal (Baud Rate) evaluando el desempeño de la demodulación
    para cada velocidad candidata del canal de audio FM.
    """

    def __init__(self):
        self.fs = config.FS_RX
        self.candidatos = config.BAUD_RATES_CANDIDATOS

        if config.MODO_VERBOSE:
            print(f"[DetectorBaudios] Inicializado. Candidatos: {self.candidatos} baudios")

    def detectar(self, señal_filtrada: np.ndarray, f_mark: float = None, f_space: float = None, segmento_inicio: int = 0, segmento_fin: int = None) -> float:
        """
        Analiza la señal filtrada de entrada y estima la velocidad nominal (Baud Rate)
        ejecutando pruebas de demodulación y seleccionando la velocidad con menor
        tasa de error de bit (BER).

        Args:
            señal_filtrada (np.ndarray): Señal de audio preprocesada por FiltroFIR.
            f_mark (float, opcional): Frecuencia real estimada del tono Mark.
            f_space (float, opcional): Frecuencia real estimada del tono Space.
            segmento_inicio (int, opcional): Índice de inicio de la ventana de análisis.

        Returns:
            float: Baud rate detectado (de entre los candidatos en config.py).
        """
        from evaluator import EvaluadorBER
        import scipy.signal as signal

        best_baud = 1200
        best_ber = 1.0

        evaluador = EvaluadorBER()
        nyq = self.fs / 2.0

        for baud in self.candidatos:
            # Filtros de Banda Adaptativos
            half_bw = max(75.0, baud / 2.0)
            b_m, a_m = signal.butter(2, [max(100.0, f_mark - half_bw)/nyq, min(nyq-100.0, f_mark + half_bw)/nyq], btype='bandpass')
            x_mark = signal.lfilter(b_m, a_m, señal_filtrada)
            
            b_s, a_s = signal.butter(2, [max(100.0, f_space - half_bw)/nyq, min(nyq-100.0, f_space + half_bw)/nyq], btype='bandpass')
            x_space = signal.lfilter(b_s, a_s, señal_filtrada)
            
            # Envolventes
            env_mark = np.abs(x_mark)
            env_space = np.abs(x_space)
            
            # Filtro Pasa-Bajos de Envolvente
            env_lp_cutoff = min(nyq - 100.0, max(20.0, 2.0 * baud))
            b_lp, a_lp = signal.butter(2, env_lp_cutoff / nyq, btype='low')
            env_mark_lp = signal.lfilter(b_lp, a_lp, env_mark)
            env_space_lp = signal.lfilter(b_lp, a_lp, env_space)
            
            # Compensación de atenuación
            mid = len(env_mark_lp) // 2
            span = min(int(2.5 * self.fs), mid)
            em_active = env_mark_lp[mid - span : mid + span]
            es_active = env_space_lp[mid - span : mid + span]
            
            peak_mark = np.percentile(em_active, 95) if len(em_active) > 0 else 1.0
            peak_space = np.percentile(es_active, 95) if len(es_active) > 0 else 1.0
            g = peak_mark / (peak_space + 1e-12)
            
            y_balanceada = env_mark_lp - g * env_space_lp
            
            # Para 1200 baudios, usamos la corrección de drift nominal
            if baud == 1200:
                N_s = 16.0236
            else:
                N_s = float(self.fs / baud)
                
            half_N = int(N_s // 2)
            
            # Rango de búsqueda de fase
            if baud == 10:
                n_ventana_rms = int(0.10 * self.fs)
                energia = np.convolve(señal_filtrada ** 2, np.ones(n_ventana_rms) / n_ventana_rms, mode='same')
                rms_local = np.sqrt(np.maximum(energia, 0))
                umbral = 0.20 * np.max(rms_local)
                indices_activos = np.where(rms_local > umbral)[0]
                inicio_rafaga = indices_activos[0] if len(indices_activos) > 0 else 0
                rango_busqueda = range(max(0, inicio_rafaga - int(N_s)), min(len(señal_filtrada), inicio_rafaga + 2 * int(N_s)), 4)
            else:
                rango_busqueda = range(segmento_inicio, segmento_inicio + int(N_s))
                
            best_ber_baud = 1.0
            for candidate_start in rango_busqueda:
                bits_cand = []
                if segmento_fin is not None:
                    max_bits = max(0, int((segmento_fin - candidate_start) / N_s))
                    limit_bits = min(127, max_bits)
                else:
                    limit_bits = 127
                for i in range(limit_bits):
                    idx = int(candidate_start + i * N_s + half_N)
                    if idx < len(y_balanceada):
                        bits_cand.append(1 if y_balanceada[idx] > 0 else 0)
                    else:
                        bits_cand.append(0)
                if not bits_cand:
                    res_cand = {'ber': 1.0}
                else:
                    res_cand = evaluador.calcular_ber(bits_cand)
                if res_cand['ber'] < best_ber_baud:
                    best_ber_baud = res_cand['ber']
                    if best_ber_baud == 0.0:
                        break
                        
            if best_ber_baud < best_ber:
                best_ber = best_ber_baud
                best_baud = baud
                if best_ber == 0.0:
                    break

        if config.MODO_VERBOSE:
            print(f"[DetectorBaudios] Clasificado a candidato: {best_baud} bd")

        return best_baud
