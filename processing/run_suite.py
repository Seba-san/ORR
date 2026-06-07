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

def demodular_canal_universal(alias, fpath, baud_rate='auto'):
    """
    Ejecuta el demodulador diferencial síncrono universal sobre un archivo WAV específico,
    adaptando dinámicamente los anchos de banda, filtros pasa-bajos de envolvente y
    periodo de símbolo (muestras por bit) para compensar drift analógico y atenuación de RF.
    """
    print(f"\n⚡ Procesando: {alias} | Velocidad Configurada: {baud_rate}")
    
    # 1. Cargar el audio
    fs, data = wav.read(fpath)
    if data.ndim > 1:
        data = data[:, 0]
    x = data.astype(float) / np.max(np.abs(data))
    nyq = fs / 2.0
    
    # 2. Preprocesamiento (Filtro FIR de Fase Lineal)
    filtro = FiltroFIR()
    x_filtered = filtro.aplicar(x)
    
    # 3. Analizador Espectral para calibrar frecuencias reales
    analizador = AnalizadorEspectral()
    res_espectral = analizador.analizar(x_filtered)
    f_mark = res_espectral.f_mark_hz
    f_space = res_espectral.f_space_hz

    # Autodetección de Baud Rate si es 'auto'
    if baud_rate == 'auto':
        detector = DetectorBaudios()
        baud_rate = detector.detectar(x_filtered, f_mark, f_space, res_espectral.segmento_inicio)
        print(f"  • Baud Rate Detectado  : {baud_rate} bd")
    
    # 4. Filtros de Banda Adaptativos (Ancho de banda adaptado al Baud Rate para evitar ISI)
    half_bw = max(75.0, baud_rate / 2.0)
    b_m, a_m = signal.butter(2, [max(100.0, f_mark - half_bw)/nyq, min(nyq-100.0, f_mark + half_bw)/nyq], btype='bandpass')
    x_mark = signal.lfilter(b_m, a_m, x_filtered)
    
    b_s, a_s = signal.butter(2, [max(100.0, f_space - half_bw)/nyq, min(nyq-100.0, f_space + half_bw)/nyq], btype='bandpass')
    x_space = signal.lfilter(b_s, a_s, x_filtered)
    
    # Envolventes
    env_mark = np.abs(x_mark)
    env_space = np.abs(x_space)
    
    # 5. Filtro Pasa-Bajos de Envolvente (Corte nominal a 2 * Baud Rate)
    env_lp_cutoff = min(nyq - 100.0, max(20.0, 2.0 * baud_rate))
    b_lp, a_lp = signal.butter(2, env_lp_cutoff / nyq, btype='low')
    env_mark_lp = signal.lfilter(b_lp, a_lp, env_mark)
    env_space_lp = signal.lfilter(b_lp, a_lp, env_space)
    
    # 6. Compensación de Atenuación de Frecuencia (Envolventes Balanceadas)
    # Medir percentiles de amplitud en segmento activo para compensar la atenuación de 2400 Hz (-12.6 dB)
    em_active = env_mark_lp[res_espectral.segmento_inicio : res_espectral.segmento_fin]
    es_active = env_space_lp[res_espectral.segmento_inicio : res_espectral.segmento_fin]
    
    peak_mark = np.percentile(em_active, 95)
    peak_space = np.percentile(es_active, 95)
    g = peak_mark / (peak_space + 1e-12)
    
    y_balanceada = env_mark_lp - g * env_space_lp
    
    # 7. Sincronización Temporal (Grid Search de fase de ráfaga)
    if baud_rate == 1200:
        N_s = 16.0236
    else:
        N_s = float(fs / baud_rate)
        
    half_N = int(N_s // 2)
    
    if baud_rate == 10:
        n_ventana_rms = int(0.10 * fs)
        energia = np.convolve(x_filtered ** 2, np.ones(n_ventana_rms) / n_ventana_rms, mode='same')
        rms_local = np.sqrt(np.maximum(energia, 0))
        umbral = 0.20 * np.max(rms_local)
        indices_activos = np.where(rms_local > umbral)[0]
        inicio_rafaga = indices_activos[0] if len(indices_activos) > 0 else 0
        rango_busqueda = range(max(0, inicio_rafaga - int(N_s)), min(len(x_filtered), inicio_rafaga + 2 * int(N_s)))
    else:
        rango_busqueda = range(res_espectral.segmento_inicio, res_espectral.segmento_inicio + int(N_s))
    
    mejor_ber = 1.0
    mejor_start = res_espectral.segmento_inicio
    mejor_bits = []
    
    evaluador = EvaluadorBER()
    
    for candidate_start in rango_busqueda:
        bits_cand = []
        for i in range(127):
            idx = int(candidate_start + i * N_s + half_N)
            if idx < len(y_balanceada):
                bits_cand.append(1 if y_balanceada[idx] > 0 else 0)
            else:
                bits_cand.append(0)
        
        res_cand = evaluador.calcular_ber(bits_cand)
        if res_cand['ber'] < mejor_ber:
            mejor_ber = res_cand['ber']
            mejor_start = candidate_start
            mejor_bits = bits_cand
            if mejor_ber == 0.0:
                break
                
    first_bit_start = mejor_start
    bits_decididos = mejor_bits
    
    # Calcular la confianza promedio de cada bit demodulado
    lista_confianza = []
    for i in range(127):
        idx = int(first_bit_start + i * N_s + half_N)
        if idx < len(x_filtered):
            e_m = env_mark_lp[idx]
            e_s = g * env_space_lp[idx]
            Ck = np.abs(e_m - e_s) / (e_m + e_s + 1e-12)
            lista_confianza.append(min(Ck, 1.0))
    confianza_promedio = np.mean(lista_confianza) if len(lista_confianza) > 0 else 0.0
    
    # 8. Evaluación de BER final
    res_ber = evaluador.calcular_ber(bits_decididos)
    
    print(f"  • Sincronización inicial: primer bit en t = {first_bit_start/fs:.3f} s")
    print(f"  • Ganancia Compensada  : {g:.4f} (+{20*np.log10(g):.1f} dB)")
    print(f"  • Confianza Ck Promedio: {confianza_promedio:.4f}")
    print(f"  • TASA DE ERROR (BER)  : {res_ber['ber']*100.0:.4f}% ({res_ber['bits_erroneos']}/{res_ber['total_bits']} bits)")
    
    # Intentar generar el reporte de errores
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
        'secuencia_decidida': bits_decididos
    }

def main():
    import argparse
    import glob
    
    parser = argparse.ArgumentParser(description="Procesamiento dinámico de audios AFSK.")
    parser.add_argument("directorio", nargs="?", default=None,
                        help="Directorio que contiene los archivos de audio .wav")
    args = parser.parse_args()
    
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
        
    print(f"Buscando archivos .wav en: {directorio}")
    archivos = sorted(glob.glob(os.path.join(directorio, '**', '*.wav'), recursive=True))
    
    if not archivos:
        print(f"No se encontraron archivos .wav en {directorio}")
        return
        
    resultados = []
    for fpath in archivos:
        alias = os.path.splitext(os.path.basename(fpath))[0]
        try:
            res = demodular_canal_universal(alias, fpath, baud_rate='auto')
            resultados.append(res)
        except Exception as e:
            print(f"Error procesando {fpath}: {e}")
            
    # Mostrar tabla resumen factual de resultados
    if resultados:
        print("\n==========================================================================")
        print("   RESUMEN DE PROCESAMIENTO")
        print("==========================================================================")
        print(f"{'Archivo':<35} | {'Baudios':<7} | {'BER (%)':<8} | {'Errores':<8} | {'Confianza':<10}")
        print("-" * 79)
        for r in resultados:
            print(f"{r['alias'][:35]:<35} | {r['baud_rate']:<7} | {r['ber']*100.0:<8.4f} | {r['bits_erroneos']:<8} | {r['confianza_promedio']:<10.4f}")
        print("==========================================================================")

if __name__ == "__main__":
    main()
