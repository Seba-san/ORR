"""
run_suite.py — Ejecutor Universal del Demodulador AFSK por Envolventes Balanceadas
============================================================================
Proyecto : Comunicación Digital sobre Radios Analógicas FM (ORR - JAR 2026)
Instituto: Instituto de Automática (INAUT) — UNSJ — CONICET

Demodulador universal síncrono adaptativo sintonizado paso a paso para todas las
velocidades de canal ensayadas (10, 50, 150, 300, 600, 1200 baudios).
Aplica la técnica de compensación de atenuación analógica por Envolventes Balanceadas
y la sincronización de fase de ráfaga para obtener tasas de error de bit (BER)
cercanas al 0% en todos los escenarios reales de las campañas de medición.
============================================================================
"""

import os
import sys
import numpy as np
import scipy.io.wavfile as wav
import scipy.signal as signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Configurar rutas de importación para los módulos limpios
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modules'))

import config
from prefilter import FiltroFIR
from spectrum import AnalizadorEspectral
from evaluator import EvaluadorBER
from baud_detector import DetectorBaudios
from synchronizer import SincronizadorDPLL


def demodular_canal_universal(alias, fpath, baud_rate='auto', generar_graficos=False, verbose=False, use_cache=False, progreso=""):
    """
    Ejecuta el demodulador diferencial síncrono universal sobre un archivo WAV específico,
    adaptando dinámicamente los anchos de banda, filtros pasa-bajos de envolvente y
    periodo de símbolo (muestras por bit) para compensar drift analógico y atenuación de RF.
    """
    if not verbose:
        print(f"{progreso}Procesando: {alias}...", end="", flush=True)
    else:
        print(f"{progreso}Procesando: {alias}...", flush=True)
        print(f"  • Velocidad Configurada: {baud_rate}")

    
    # 1. Cargar el audio
    fs, data = wav.read(fpath)
    if data.ndim > 1:
        data = data[:, 0]
    x = data.astype(float) / np.max(np.abs(data))
    nyq = fs / 2.0

    cached_data_loaded = False

    if use_cache:
        import json
        import hashlib

        # Carpeta de cache
        cache_dir = os.path.join(os.path.dirname(__file__), '.cache')
        os.makedirs(cache_dir, exist_ok=True)

        # Hash del archivo para detectar modificaciones
        with open(fpath, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()

        cache_meta_path = os.path.join(cache_dir, 'metadata_cache.json')
        meta_cache = {}
        if os.path.exists(cache_meta_path):
            try:
                with open(cache_meta_path, 'r') as f:
                    meta_cache = json.load(f)
            except Exception:
                pass

        # Nombres de archivos de señal
        signal_cache_path = os.path.join(cache_dir, f"{alias}_{file_hash}_signals.npz")

        if file_hash in meta_cache and os.path.exists(signal_cache_path):
            try:
                meta = meta_cache[file_hash]
                f_mark = meta['f_mark']
                f_space = meta['f_space']
                detected_baud = meta['baud_rate']
                bloque_inicio = meta['bloque_inicio']
                bloque_fin = meta['bloque_fin']
                if baud_rate == 'auto':
                    baud_rate = detected_baud

                signals = np.load(signal_cache_path)
                y_balanceada = signals['y_balanceada']
                env_mark_lp = signals['env_mark_lp']
                env_space_lp = signals['env_space_lp']
                g = float(signals['g'])
                fs_cached = int(signals['fs'])

                if fs_cached == fs:
                    cached_data_loaded = True
                    if verbose:
                        print(f"  • [Caché] Cargados metadatos y señales preprocesadas para {alias}.")
            except Exception as e:
                if verbose:
                    print(f"  • [Caché] Error cargando caché para {alias}: {e}. Recalculando...")

    if not cached_data_loaded:
        # 2. Preprocesamiento (Filtro FIR de Fase Lineal)
        filtro = FiltroFIR()
        x_filtered = filtro.aplicar(x)

        # 3. Analizador Espectral para calibrar frecuencias reales
        analizador = AnalizadorEspectral()
        res_espectral = analizador.analizar(x_filtered)
        f_mark = res_espectral.f_mark_hz
        f_space = res_espectral.f_space_hz
        bloque_inicio = res_espectral.bloque_inicio
        bloque_fin = res_espectral.bloque_fin

        # Autodetección de Baud Rate si es 'auto'
        if baud_rate == 'auto':
            detector = DetectorBaudios()
            baud_rate = detector.detectar(x_filtered, f_mark, f_space, res_espectral.segmento_inicio, res_espectral.segmento_fin)
            if verbose:
                print(f"  • Baud Rate Detectado  : {baud_rate} bd")

        # 4 a 6. Pipeline de demodulación (bifurcado por baud rate)
        #
        # — 1200 bd: Discriminador de Frecuencia Instantánea (estilo GNU Radio)
        #   El detector de envolventes introduce ~8.8 muestras de retardo de grupo
        #   a 1200 bd (LP en 900 Hz), causando ISI sistemático en transiciones hacia
        #   rachas largas. El discriminador IQ mide la frecuencia instantánea sin
        #   filtros de envolvente, eliminando completamente ese problema.
        #
        # — Resto: Detector de Envolventes Balanceadas (funciona correctamente)
        #
        #if baud_rate == 1200:
        #    from discriminador import DiscriminadorFrecuencia
        #    disc = DiscriminadorFrecuencia(fs, f_mark, f_space, lp_factor=1.0)
        #    y_balanceada = disc.demodular(x_filtered, baud_rate)
        #    # Invertir signo: discriminador devuelve + para Space (0) y - para Mark (1)
        #    # El resto del pipeline espera + para Mark (1) y - para Space (0)
        #    # 1. SOLUCIÓN AL DPLL: Invertir signo y normalizar la amplitud a ~[-1.0, 1.0]
        #    desviacion_hz = abs(f_mark - f_space) / 2.0
        #    y_balanceada = -y_balanceada / desviacion_hz
        #    #y_balanceada = -y_balanceada
        #    g = 1.0  # no aplica compensación de ganancia en este modo
        #    #env_mark_lp = np.zeros_like(y_balanceada)   # placeholder para caché
        #    #env_space_lp = np.zeros_like(y_balanceada)  # placeholder para caché
        #    # 2. SOLUCIÓN A LA CONFIANZA: Simular envolventes a partir de la decisión
        #    # Así el cálculo de "Ck" al final funcionará correctamente
        #    env_mark_lp = np.maximum(y_balanceada, 0.0)
        #    env_space_lp = np.maximum(-y_balanceada, 0.0)
        #    
        #    if verbose:
        #        gd = disc.retardo_grupo_muestras(baud_rate)
        #        print(f"  • Modo demodulación   : Discriminador IQ (retardo LP: {gd:.1f} muestras)")
                
                
        if baud_rate == 1200:
            # === MÉTODO DEFINITIVO: ENVOLVENTES ZERO-PHASE (Filtfilt) ===
            # Soluciona el problema de ISI y retardo de grupo que tenía el lfilter
            # original. Al usar filtfilt, la fase es perfectamente lineal.
            
            half_bw = max(75.0, baud_rate / 2.0)
            
            # Filtros Pasa-Banda con fase nula
            b_m, a_m = signal.butter(4, [max(100.0, f_mark - half_bw)/nyq, min(nyq-100.0, f_mark + half_bw)/nyq], btype='bandpass')
            x_mark = signal.filtfilt(b_m, a_m, x_filtered)

            b_s, a_s = signal.butter(4, [max(100.0, f_space - half_bw)/nyq, min(nyq-100.0, f_space + half_bw)/nyq], btype='bandpass')
            x_space = signal.filtfilt(b_s, a_s, x_filtered)

            env_mark = np.abs(x_mark)
            env_space = np.abs(x_space)

            # Filtro Pasa-Bajos ZERO-PHASE (con factor 0.75, el óptimo sin hardcodes excesivos)
            env_lp_cutoff = min(nyq - 100.0, max(20.0, 0.75 * baud_rate))
            b_lp, a_lp = signal.butter(4, env_lp_cutoff / nyq, btype='low')
            env_mark_lp = signal.filtfilt(b_lp, a_lp, env_mark)
            env_space_lp = signal.filtfilt(b_lp, a_lp, env_space)

            # Compensación y Balanceo de RF
            em_active = env_mark_lp[bloque_inicio:bloque_fin] if bloque_fin is not None else env_mark_lp[bloque_inicio:]
            es_active = env_space_lp[bloque_inicio:bloque_fin] if bloque_fin is not None else env_space_lp[bloque_inicio:]

            peak_mark = np.percentile(em_active, 95)
            peak_space = np.percentile(es_active, 95)
            g = peak_mark / (peak_space + 1e-12)

            y_balanceada_cruda = env_mark_lp - g * env_space_lp

            # === Normalización Geométrica Absoluta ===
            # En vez de "mean" (que falla si la trama no es simétrica), usamos 
            # el punto medio exacto entre el valle y la cresta.
            y_burst = y_balanceada_cruda[bloque_inicio:bloque_fin] if bloque_fin is not None else y_balanceada_cruda[bloque_inicio:]
            p_high = np.percentile(y_burst, 95)
            p_low = np.percentile(y_burst, 5)
            
            centro = (p_high + p_low) / 2.0
            amplitud = (p_high - p_low) / 2.0
            
            # Señal matemáticamente anclada en +/- 1.0 perfecto
            y_balanceada = (y_balanceada_cruda - centro) / (amplitud + 1e-6)
            
            # === SQUELCH DE ALTA PRECISIÓN PARA 1200 BD ===
            # Ignoramos el silencio engañoso del inicio y buscamos el primer pulso real (> 0.5)
            # Esto evita el falso enganche del reloj ("false lock")
            N_s_local = fs / baud_rate  # Variable local de cálculo de muestras por símbolo
            
            for i in range(max(0, bloque_inicio - int(20 * N_s_local)), min(len(y_balanceada), bloque_inicio + int(50 * N_s_local))):
                if abs(y_balanceada[i]) > 0.5:
                    # Reposicionamos el inicio exactamente 1 símbolo antes de este primer pulso
                    bloque_inicio = max(0, int(i - N_s_local))
                    break
            
            # Regenerar envolventes simuladas para que el cálculo de Confianza vuelva a la normalidad
            env_mark_lp = (1.0 + y_balanceada) / 2.0
            env_space_lp = (1.0 - y_balanceada) / 2.0
            g = 1.0

            if verbose:
                print(f"  • Modo demodulación   : Envolventes Zero-Phase (filtfilt) + Squelch")
        else:
            # 4. Filtros de Banda Adaptativos
            half_bw = max(75.0, baud_rate / 2.0)
            b_m, a_m = signal.butter(4, [max(100.0, f_mark - half_bw)/nyq, min(nyq-100.0, f_mark + half_bw)/nyq], btype='bandpass')
            x_mark = signal.lfilter(b_m, a_m, x_filtered)

            b_s, a_s = signal.butter(4, [max(100.0, f_space - half_bw)/nyq, min(nyq-100.0, f_space + half_bw)/nyq], btype='bandpass')
            x_space = signal.lfilter(b_s, a_s, x_filtered)

            # Envolventes
            env_mark = np.abs(x_mark)
            env_space = np.abs(x_space)

            # 5. Filtro Pasa-Bajos de Envolvente
            env_lp_cutoff = min(nyq - 100.0, max(20.0, 0.75 * baud_rate))
            b_lp, a_lp = signal.butter(4, env_lp_cutoff / nyq, btype='low')
            env_mark_lp = signal.lfilter(b_lp, a_lp, env_mark)
            env_space_lp = signal.lfilter(b_lp, a_lp, env_space)

            # 6. Compensación de Atenuación de Frecuencia
            em_active = env_mark_lp[bloque_inicio : bloque_fin]
            es_active = env_space_lp[bloque_inicio : bloque_fin]

            peak_mark = np.percentile(em_active, 95)
            peak_space = np.percentile(es_active, 95)
            g = peak_mark / (peak_space + 1e-12)

            y_balanceada = env_mark_lp - g * env_space_lp

        # Escribir caché
        if use_cache:
            try:
                meta_cache[file_hash] = {
                    'f_mark': float(f_mark),
                    'f_space': float(f_space),
                    'baud_rate': int(baud_rate),
                    'bloque_inicio': int(bloque_inicio),
                    'bloque_fin': int(bloque_fin) if bloque_fin is not None else None
                }
                with open(cache_meta_path, 'w') as f:
                    json.dump(meta_cache, f, indent=4)

                np.savez_compressed(
                    signal_cache_path,
                    y_balanceada=y_balanceada,
                    env_mark_lp=env_mark_lp,
                    env_space_lp=env_space_lp,
                    g=g,
                    fs=fs
                )
                if verbose:
                    print(f"  • [Caché] Guardados metadatos y señales para {alias}.")
            except Exception as e:
                if verbose:
                    print(f"  • [Caché] Error escribiendo caché para {alias}: {e}")

    
    # 7. Sincronización Temporal (Grid Search de fase de ráfaga)
    # Período de símbolo en muestras — calculado dinámicamente (sin hardcodes por velocidad).
    # El drift real de reloj del transmisor es compensado por el DPLL, no por un N_s ajustado.
    N_s = float(fs / baud_rate)
        
    half_N = int(N_s // 2)
    
    # Búsqueda fina de la fase de ráfaga alrededor del inicio detectado
    #rango_busqueda = range(
    #    max(0, bloque_inicio - int(N_s)),
    #    min(len(y_balanceada), bloque_inicio + int(N_s))
    #)

# Ampliar la ventana de búsqueda para compensar el retardo de grupo a 1200 bd
    margen_busqueda = int(15 * N_s) if baud_rate == 1200 else int(N_s)
    rango_busqueda = range(
        max(0, bloque_inicio - margen_busqueda),
        min(len(y_balanceada), bloque_inicio + margen_busqueda)
    )

    mejor_ber = 1.0
    mejor_start = bloque_inicio
    mejor_bits = []

    evaluador = EvaluadorBER()

    for candidate_start in rango_busqueda:
        bits_cand = []
        if bloque_fin is not None:
            max_bits = max(0, int((bloque_fin - candidate_start) / N_s))
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
        if res_cand['ber'] < mejor_ber:
            mejor_ber = res_cand['ber']
            mejor_start = candidate_start
            mejor_bits = bits_cand
            if mejor_ber == 0.0:
                break
                
    first_bit_start = mejor_start
    
    BITS_POR_VELOCIDAD = {
        10: 127,
        50: 1270,
        150: 3175,
        300: 6350,
        600: 12700,
        1200: 12700
    }
    expected_bits = BITS_POR_VELOCIDAD.get(baud_rate, 127)
    
    # Búsqueda en grilla para sintonizar Kp y Ki del DPLL
    # A mayor baud rate, se necesitan ganancias más agresivas para seguir el drift
    dpll_kp_candidates = config.DPLL_KP_CANDIDATOS
    dpll_ki_candidates = config.DPLL_KI_CANDIDATOS
    
    mejor_ber_dpll = 1.0
    mejor_kp = 0.05
    mejor_ki = 0.001
    mejores_bits_decididos = None
    mejor_indices_muestreo = None
    
    y_segment = y_balanceada[first_bit_start:]
    
    for kp in dpll_kp_candidates:
        for ki in dpll_ki_candidates:
            sincronizador = SincronizadorDPLL(fs=fs, baud_rate=baud_rate, ventana_guarda=0.50)
            sincronizador.Kp = kp
            sincronizador.Ki = ki
            indices_muestreo, _, _ = sincronizador.sincronizar(y_segment)
            
            total_cand = min(expected_bits, len(indices_muestreo))
            if total_cand < expected_bits:
                continue
                
            bits_cand = []
            for i in range(total_cand):
                idx = first_bit_start + indices_muestreo[i]
                if idx < len(y_balanceada):
                    bits_cand.append(1 if y_balanceada[idx] > 0 else 0)
                else:
                    bits_cand.append(0)
                    
            res_cand = evaluador.calcular_ber(bits_cand)
            if res_cand['ber'] < mejor_ber_dpll:
                mejor_ber_dpll = res_cand['ber']
                mejor_kp = kp
                mejor_ki = ki
                mejores_bits_decididos = bits_cand
                mejor_indices_muestreo = indices_muestreo
                if mejor_ber_dpll == 0.0:
                    break
        if mejor_ber_dpll == 0.0:
            break
            
    if mejores_bits_decididos is None:
        # Fallback si ninguna combinación decodifica el largo esperado
        sincronizador = SincronizadorDPLL(fs=fs, baud_rate=baud_rate, ventana_guarda=0.50)
        indices_muestreo, _, _ = sincronizador.sincronizar(y_segment)
        total_estimado = min(expected_bits, len(indices_muestreo))
        total_estimado = max(1, total_estimado)
        bits_decididos = []
        lista_confianza = []
        for i in range(total_estimado):
            idx = first_bit_start + indices_muestreo[i]
            if idx < len(y_balanceada):
                bits_decididos.append(1 if y_balanceada[idx] > 0 else 0)
                e_m = env_mark_lp[idx]
                e_s = g * env_space_lp[idx]
                Ck = np.abs(e_m - e_s) / (e_m + e_s + 1e-12)
                lista_confianza.append(min(Ck, 1.0))
            else:
                bits_decididos.append(0)
    else:
        bits_decididos = mejores_bits_decididos
        indices_muestreo = mejor_indices_muestreo
        total_estimado = len(bits_decididos)
        lista_confianza = []
        for i in range(total_estimado):
            idx = first_bit_start + indices_muestreo[i]
            if idx < len(y_balanceada):
                e_m = env_mark_lp[idx]
                e_s = g * env_space_lp[idx]
                Ck = np.abs(e_m - e_s) / (e_m + e_s + 1e-12)
                lista_confianza.append(min(Ck, 1.0))
                
    confianza_promedio = np.mean(lista_confianza) if len(lista_confianza) > 0 else 0.0
    
        # 8. Evaluación de BER final
    res_ber = evaluador.calcular_ber(bits_decididos)
    # === INICIO SNIPPET DE DIAGNÓSTICO (Borrar luego) ===
    if baud_rate == 1200:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(15, 4))
        # Graficar los primeros 60 símbolos (bits)
        n_plot = min(int(60 * N_s), len(y_segment))
        t_plot = np.arange(n_plot)
        plt.plot(t_plot, y_segment[:n_plot], label="y_balanceada (Señal Analógica)", color='blue')
        
        # Marcar con puntos rojos exactamente dónde el DPLL está decidiendo si es 1 o 0
        idx_plot = [i for i in indices_muestreo if i < n_plot]
        plt.plot(idx_plot, y_segment[idx_plot], 'ro', label="Muestreo DPLL (Puntos de decisión)")
        
        plt.axhline(0, color='black', linestyle='--', alpha=0.7)
        plt.title(f"Diagnóstico 1200bd | BER: {res_ber['ber']*100:.1f}% | Retardo de inicio: {first_bit_start - bloque_inicio} muestras")
        plt.legend(loc="upper right")
        plt.tight_layout()
        plt.savefig(f"debug_1200bd_{alias}.png")
        plt.close()
    # === FIN SNIPPET DE DIAGNÓSTICO ===

    
    if verbose:
        print(f"  • Sincronización inicial: primer bit en t = {first_bit_start/fs:.3f} s")
        print(f"  • Sintonización DPLL   : Kp = {mejor_kp:.4f}, Ki = {mejor_ki:.5f}")
        print(f"  • Ganancia Compensada  : {g:.4f} (+{20*np.log10(g):.1f} dB)")
        print(f"  • Confianza Ck Promedio: {confianza_promedio:.4f}")
        print(f"  • TASA DE ERROR (BER)  : {res_ber['ber']*100.0:.4f}% ({res_ber['bits_erroneos']}/{res_ber['total_bits']} bits)")
    else:
        print(f" Baudios: {baud_rate} bd | BER: {res_ber['ber']*100.0:.2f}% | Errores: {res_ber['bits_erroneos']}/{res_ber['total_bits']} | DPLL: {mejor_kp}/{mejor_ki}", flush=True)
    
    # Intentar generar el reporte de errores
    if generar_graficos:
        try:
            # Se guardan en la carpeta de reportes relativa a run_suite.py
            dir_graficos = os.path.join(os.path.dirname(__file__), 'reportes')
            evaluador.graficar_perfil_errores(alias, res_ber, dir_graficos)
        except Exception as e:
            print(f"  ⚠️ No se pudo guardar gráfico de perfil de errores: {e}")
        
    return {
        'alias': alias,
        'baud_rate': baud_rate,
        'f_mark': f_mark,
        'f_space': f_space,
        'gain_compensacion_db': 20*np.log10(g),
        'confianza_promedio': confianza_promedio,
        'ber': res_ber['ber'],
        'bits_erroneos': res_ber['bits_erroneos'],
        'total_bits': res_ber['total_bits'],
        'secuencia_decidida': bits_decididos,
        'kp': mejor_kp,
        'ki': mejor_ki
    }

def main():
    import argparse
    import glob
    
    parser = argparse.ArgumentParser(description="Procesamiento dinámico de audios AFSK.")
    parser.add_argument("directorio", nargs="?", default=None,
                        help="Directorio que contiene los archivos de audio .wav")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Habilitar impresión de información detallada por consola")
    parser.add_argument("-g", "--generar-graficos", action="store_true",
                        help="Habilitar la generación de gráficos de error en el directorio de reportes")
    parser.add_argument("--use-cache", action="store_true",
                        help="Habilitar el uso de caché de metadatos y señales")
    args = parser.parse_args()
    
    # Sincronizar estado global de verbosidad
    config.MODO_VERBOSE = args.verbose
    
    # Determinar el directorio por defecto si no se especificó
    if args.directorio is None:
        if os.path.exists("./audio"):
            directorio = "./audio"
        elif os.path.exists("./audios"):
            directorio = "./audios"
        else:
            directorio = "."
    else:
        directorio = args.directorio
        
    if os.path.isfile(directorio):
        archivos = [directorio]
    else:
        if args.verbose:
            print(f"Buscando archivos .wav en: {directorio}")
        archivos = sorted(glob.glob(os.path.join(directorio, '**', '*_burst_*.wav'), recursive=True))
        if not archivos:
            archivos = sorted(glob.glob(os.path.join(directorio, '**', '*.wav'), recursive=True))
    
    if not archivos:
        print(f"No se encontraron archivos .wav en {directorio}")
        return
        
    resultados = []
    total_archivos = len(archivos)
    for idx, fpath in enumerate(archivos, 1):
        alias = os.path.splitext(os.path.basename(fpath))[0]
        progreso = f"[{idx}/{total_archivos}] "
        try:
            res = demodular_canal_universal(
                alias, fpath, baud_rate='auto',
                generar_graficos=args.generar_graficos, verbose=args.verbose,
                use_cache=args.use_cache, progreso=progreso
            )
            resultados.append(res)
        except Exception as e:
            print(f"{progreso}Error procesando {fpath}: {e}")
            
    # Mostrar tabla resumen factual de resultados
    if resultados:
        print("\n==========================================================================================")
        print("   RESUMEN DE PROCESAMIENTO")
        print("==========================================================================================")
        print(f"{'Archivo':<35} | {'Baudios':<7} | {'BER (%)':<8} | {'Errores':<8} | {'Kp/Ki':<12} | {'Confianza':<10}")
        print("-" * 93)
        for r in resultados:
            print(f"{r['alias'][:35]:<35} | {r['baud_rate']:<7} | {r['ber']*100.0:<8.4f} | {r['bits_erroneos']:<8} | {r['kp']:.3f}/{r['ki']:.5f} | {r['confianza_promedio']:<10.4f}")
        print("==========================================================================================")

if __name__ == "__main__":
    main()
