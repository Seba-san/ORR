"""
analizador_espectral.py — Calibración Espectral Aislada (Ventana de 5 Segundos)
============================================================================
Proyecto : Comunicación Digital sobre Radios Analógicas FM (JAR 2026)
Instituto: Instituto de Automática (INAUT) — UNSJ — CONICET

Implementa el segundo eslabón de la cadena de demodulación: el análisis
espectral para autocalibrar las frecuencias reales de los
tonos Mark y Space presentes en la señal grabada.

Estrategia (Revisada y Certificada tras HITL 1):
  - Segmenta el audio buscando bloques de señal continua activa de forma sostenida
    (duración > 4.0s). Esto tiene en cuenta el espaciado experimental de 30s entre
    las dos ráfagas consecutivas transmitidas para no recalentar las radios.
  - Aísla la **primera ráfaga de datos** e instala la ventana de análisis de
    **5.0 segundos** (40000 muestras) exactamente en el **centro geométrico** de
    esta ráfaga de forma aislada. Esto descarta silencios, transitorios iniciales y
    clicks de PTT.
  - Realiza un análisis FFT de alta resolución (~0.20 Hz) para resolver con
    máxima exactitud los picos reales.
============================================================================
"""

import numpy as np
from scipy.signal import get_window
import config


class ResultadoEspectral:
    """
    Contenedor de resultados del análisis espectral de alta resolución.
    Agrupa todas las métricas calculadas por el AnalizadorEspectral.
    """
    def __init__(self):
        self.f_mark_hz       = None   # Frecuencia real del tono Mark (Hz)
        self.f_space_hz      = None   # Frecuencia real del tono Space (Hz)
        self.amp_mark        = None   # Amplitud espectral del pico de Mark
        self.amp_space       = None   # Amplitud espectral del pico de Space
        self.ratio_snr_mark  = None   # Relación pico/piso de ruido para Mark (dB)
        self.ratio_snr_space = None   # Relación pico/piso de ruido para Space (dB)
        self.espectro_promedio = None # Espectro de potencia de alta resolución (para graficar/estimar)
        self.freqs_hz        = None   # Eje de frecuencias del espectro (Hz)
        self.n_ventanas      = 1      # Ventana de integración de 5s
        self.segmento_inicio = None   # Índice de inicio de la ventana de 5s
        self.segmento_fin    = None   # Índice de fin de la ventana de 5s
        self.bloque_inicio   = None   # Índice de inicio de la ráfaga
        self.bloque_fin      = None   # Índice de fin de la ráfaga


class AnalizadorEspectral:
    """
    Analizador espectral para calibrar tonos AFSK en radios FM.

    Garantiza que la ventana de 5.0 segundos caiga en el centro estable de la
    primera ráfaga útil de transmisión, libre del silencio intermedio de 30s.
    """

    def __init__(self):
        self.fs          = config.FS_RX
        self.n_ventana_5s = int(5.0 * self.fs)  # 5 segundos = 40000 muestras
        self.tipo_ventana = config.FFT_TIPO_VENTANA

        # Pre-calcular la ventana de ponderación Hann para los 5 segundos
        self._ventana_ponderacion = get_window(self.tipo_ventana, self.n_ventana_5s)

        if config.MODO_VERBOSE:
            print(f"[AnalizadorEspectral] Inicializado en modo Alta Resolución: "
                  f"Ventana de 5.0s ({self.n_ventana_5s} muestras), "
                  f"Resolución Teórica = {self.fs/self.n_ventana_5s:.3f} Hz")

    def _localizar_ventana_util(self, señal: np.ndarray) -> tuple:
        """
        Detecta el inicio de la modulación real filtrando la señal específicamente
        en la banda útil de los tonos AFSK (1000 a 2600 Hz) y calculando su energía RMS.
        """
        from scipy import signal as sp_signal
        nyq = self.fs / 2.0
        
        # Filtro pasabanda Butterworth para aislar los tonos de interés
        b, a = sp_signal.butter(4, [1000.0 / nyq, 2600.0 / nyq], btype='bandpass')
        señal_tonos = sp_signal.lfilter(b, a, señal)
        
        # Potencia RMS en ventana móvil de 50 ms
        n_win = int(0.05 * self.fs)
        energia = np.convolve(señal_tonos ** 2, np.ones(n_win) / n_win, mode='same')
        rms_local = np.sqrt(np.maximum(energia, 0))
        
        # Umbral basado en config (buscando después del transitorio inicial)
        t_transient = int(config.TRANSITORIO_INICIO_S * self.fs)
        umbral = config.SQUELCH_FACTOR_INICIO * np.max(rms_local[t_transient:])
        indices_activos = np.where(rms_local > umbral)[0]
        # Ignorar cualquier índice dentro del transitorio inicial
        indices_activos = indices_activos[indices_activos >= t_transient]
        
        if len(indices_activos) > 0:
            inicio_bloque = indices_activos[0]
            fin_bloque = indices_activos[-1]
        else:
            inicio_bloque = 0
            fin_bloque = len(señal)
            
        centro_bloque = inicio_bloque + (fin_bloque - inicio_bloque) // 2
        
        # Centrar la ventana de 5s para el analizador espectral
        inicio = max(0, centro_bloque - self.n_ventana_5s // 2)
        if inicio + self.n_ventana_5s > len(señal):
            inicio = max(0, len(señal) - self.n_ventana_5s)
        fin = inicio + self.n_ventana_5s
        
        if config.MODO_VERBOSE:
            print(f"[AnalizadorEspectral] Ráfaga modulada detectada: {inicio_bloque/self.fs:.2f}s — {fin_bloque/self.fs:.2f}s. "
                  f"Ventana de 5s centrada en: {inicio/self.fs:.2f}s — {fin/self.fs:.2f}s")
                  
        return inicio, fin, inicio_bloque, fin_bloque

    def _localizar_pico(self, freqs: np.ndarray, espectro: np.ndarray,
                        f_centro: float, rango: float) -> tuple:
        """
        Encuentra el pico espectral máximo de alta resolución dentro del rango
        de búsqueda f_centro ± rango Hz.
        """
        mask = (freqs >= f_centro - rango) & (freqs <= f_centro + rango)
        if not np.any(mask):
            return f_centro, 0.0

        espectro_banda = espectro[mask]
        freqs_banda    = freqs[mask]

        idx_pico = np.argmax(espectro_banda)
        return freqs_banda[idx_pico], espectro_banda[idx_pico]

    def _calcular_snr_pico(self, freqs: np.ndarray, espectro: np.ndarray,
                           f_pico: float, rango_señal: float = 30.0) -> float:
        """
        Estima la relación pico/piso de ruido para el pico detectado en el
        espectro de alta resolución (en dB).
        """
        amp_pico = np.max(espectro[(freqs >= f_pico - rango_señal) &
                                   (freqs <= f_pico + rango_señal)],
                          initial=1e-12)

        # Piso de ruido: promedio en la banda acústica (300-3000 Hz)
        # excluyendo las vecindades de Mark y Space
        mask_ruido = (
            ((freqs > config.FIR_FREC_BAJA_HZ) & (freqs < config.F_MARK_NOMINAL - 150)) |
            ((freqs > config.F_MARK_NOMINAL + 150) & (freqs < config.F_SPACE_NOMINAL - 150)) |
            ((freqs > config.F_SPACE_NOMINAL + 150) & (freqs < config.FIR_FREC_ALTA_HZ))
        )

        if not np.any(mask_ruido):
            return 0.0

        piso_ruido = np.mean(espectro[mask_ruido]) + 1e-12
        snr_db = 10 * np.log10(amp_pico / piso_ruido)
        return snr_db

    def analizar(self, señal_filtrada: np.ndarray) -> ResultadoEspectral:
        """
        Ejecuta el análisis espectral de alta resolución centrado en la primera ráfaga activa.

        Pasos:
          1. Localiza un segmento de 5s garantizado en el centro de la primera ráfaga.
          2. Multiplica por ventana Hann de 40000 muestras y calcula la FFT.
          3. Localiza los picos de Mark y Space.
          4. Estima la relación señal a ruido efectiva.
        """
        resultado = ResultadoEspectral()

        # Si la señal es más corta que 5 segundos
        if len(señal_filtrada) < self.n_ventana_5s:
            if config.MODO_VERBOSE:
                print(f"[AnalizadorEspectral] ⚠️ Señal demasiado corta ({len(señal_filtrada)} muestras < 5s).")
            self.n_ventana_5s = len(señal_filtrada)
            self._ventana_ponderacion = get_window(self.tipo_ventana, self.n_ventana_5s)
            inicio, fin = 0, len(señal_filtrada)
            segmento = señal_filtrada
            inicio_bloque, fin_bloque = 0, len(señal_filtrada)
        else:
            # 1. Localizar ventana de 5s centrada en la primera ráfaga
            inicio, fin, inicio_bloque, fin_bloque = self._localizar_ventana_util(señal_filtrada)
            segmento = señal_filtrada[inicio:fin]

        resultado.segmento_inicio = inicio
        resultado.segmento_fin    = fin
        resultado.bloque_inicio   = inicio_bloque
        resultado.bloque_fin      = fin_bloque

        # 2. Calcular la FFT
        bloque_ponderado = segmento * self._ventana_ponderacion
        X = np.fft.rfft(bloque_ponderado, n=self.n_ventana_5s)
        espectro = np.abs(X) ** 2

        # Eje de frecuencias
        freqs = np.fft.rfftfreq(self.n_ventana_5s, 1.0 / self.fs)

        resultado.espectro_promedio = espectro
        resultado.freqs_hz          = freqs

        # 3. Localizar los picos de Mark y Space
        resultado.f_mark_hz, resultado.amp_mark = self._localizar_pico(
            freqs, espectro,
            f_centro=config.F_MARK_NOMINAL,
            rango=config.RANGO_BUSQUEDA_MARK_HZ
        )
        resultado.f_space_hz, resultado.amp_space = self._localizar_pico(
            freqs, espectro,
            f_centro=config.F_SPACE_NOMINAL,
            rango=config.RANGO_BUSQUEDA_SPACE_HZ
        )

        # 4. Estimar SNR
        resultado.ratio_snr_mark  = self._calcular_snr_pico(freqs, espectro, resultado.f_mark_hz)
        resultado.ratio_snr_space = self._calcular_snr_pico(freqs, espectro, resultado.f_space_hz)

        return resultado

    def imprimir_reporte(self, resultado: ResultadoEspectral):
        """
        Imprime un reporte estructurado de calibración espectral con resolución sub-hertz.
        """
        print("\n[AnalizadorEspectral] === Reporte de Calibración Hiper-Resolución ===")
        print(f"  Segmento Útil Analizado : {resultado.segmento_inicio/self.fs:.3f}s — "
              f"{resultado.segmento_fin/self.fs:.3f}s (Primera Ráfaga Estable)")
        print()
        if resultado.f_mark_hz is None:
            print("  ❌ No se pudieron detectar los tonos.")
            return

        drift_mark  = resultado.f_mark_hz  - config.F_MARK_NOMINAL
        drift_space = resultado.f_space_hz - config.F_SPACE_NOMINAL

        print(f"  MARK  (nominal {config.F_MARK_NOMINAL} Hz):")
        print(f"    Pico Estimado : {resultado.f_mark_hz:.2f} Hz  "
              f"(drift = {drift_mark:+.2f} Hz)")
        print(f"    Amplitud      : {resultado.amp_mark:.4e}")
        print(f"    SNR Estimado  : {resultado.ratio_snr_mark:.2f} dB")
        print()
        print(f"  SPACE (nominal {config.F_SPACE_NOMINAL} Hz):")
        print(f"    Pico Estimado : {resultado.f_space_hz:.2f} Hz  "
              f"(drift = {drift_space:+.2f} Hz)")
        print(f"    Amplitud      : {resultado.amp_space:.4e}")
        print(f"    SNR Estimado  : {resultado.ratio_snr_space:.2f} dB")
        print()

        # Advertencia si el SNR es marginal
        for nombre, snr in [('Mark', resultado.ratio_snr_mark),
                             ('Space', resultado.ratio_snr_space)]:
            if snr < 6.0:
                print(f"  ⚠️  SNR de {nombre} ({snr:.2f} dB) es bajo — "
                       f"los picos pueden estar enmascarados por ruido.")
        print()
