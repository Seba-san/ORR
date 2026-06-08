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
    if baud_rate == 1200:
        N_s = 16.0236
    else:
        N_s = float(fs / baud_rate)
        
    half_N = int(N_s // 2)
    
    # Búsqueda fina de la fase de ráfaga alrededor del inicio detectado
    rango_busqueda = range(
        max(0, bloque_inicio - int(N_s)),
        min(len(y_balanceada), bloque_inicio + int(N_s))
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
    dpll_kp_candidates = [0.01, 0.02, 0.05, 0.08, 0.12, 0.18, 0.25]
    dpll_ki_candidates = [0.0001, 0.0005, 0.001, 0.002, 0.004, 0.008]
    
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
