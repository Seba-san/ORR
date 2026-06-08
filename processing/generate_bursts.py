#!/usr/bin/env python3
"""
generate_bursts.py — Herramienta de Segmentación Automática de Ráfagas AFSK
============================================================================
Proyecto : Outdoor Radio Robotics (ORR)
Instituto: Instituto de Automática (INAUT) — UNSJ — CONICET

Este script procesa archivos de audio WAV continuos de telemetría y extrae
automáticamente las ráfagas (bursts) activas de modulación digital, guardándolas
como archivos independientes. Soporta optimización automática de umbral
mediante grilla de búsqueda y es completamente configurable por línea de comandos.
============================================================================
"""

import os
import sys
import glob
import argparse
import numpy as np
import scipy.io.wavfile as wav
import scipy.signal as signal

# Configurar rutas para importar módulos del receptor
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modules'))
try:
    import config
    FS_NOMINAL = config.FS_RX
except ImportError:
    FS_NOMINAL = 19200


def es_rafaga_afsk_valida(segmento_float, fs, f_mark=1200, f_space=2400, snr_threshold=10.0):
    """
    Verifica espectralmente si un segmento de audio contiene tonos AFSK reales
    (Mark a 1200 Hz y Space a 2400 Hz) con suficiente relación señal-ruido.
    Retorna una tupla (es_valida, snr_estimada).
    """
    n = len(segmento_float)
    # Tomar hasta 1.0 segundo del centro del segmento
    n_seg = min(n, int(1.0 * fs))
    if n_seg < int(0.5 * fs):  # Al menos 0.5s para análisis
        return False, 0.0
        
    start_idx = (n - n_seg) // 2
    segmento = segmento_float[start_idx : start_idx + n_seg]
    
    # Calcular espectro de amplitud (FFT) con ventana Hann
    window = np.hanning(n_seg)
    X = np.fft.rfft(segmento * window)
    mag = np.abs(X)
    freqs = np.fft.rfftfreq(n_seg, 1.0 / fs)
    
    # Buscar energía en los tonos (Mark +- 120 Hz y Space +- 120 Hz)
    mask_mark = (freqs >= f_mark - 120) & (freqs <= f_mark + 120)
    mask_space = (freqs >= f_space - 120) & (freqs <= f_space + 120)
    
    if not np.any(mask_mark) or not np.any(mask_space):
        return False, 0.0
        
    # Pico de amplitud en las bandas de Mark y Space
    peak_mark = np.max(mag[mask_mark])
    peak_space = np.max(mag[mask_space])
    energia_tonos = peak_mark + peak_space
    
    # Ruido de referencia: promedio en la banda de audio (300 a 3000 Hz) excluyendo los tonos
    mask_ruido = (freqs >= 300) & (freqs <= 3000) & (~mask_mark) & (~mask_space)
    if not np.any(mask_ruido):
        return False, 0.0
        
    promedio_ruido = np.mean(mag[mask_ruido])
    
    # Relación de amplitud tono/ruido
    snr_estimada = energia_tonos / (promedio_ruido + 1e-12)
    
    return (snr_estimada > snr_threshold), snr_estimada


def detectar_bloques_activos(x_filtered, fs, threshold_ratio, duracion_minima_s, snr_threshold):
    """
    Detecta los bloques activos en la señal filtrada usando un umbral de energía.
    Retorna una lista de tuplas (inicio, fin, promedio_snr) de los bloques válidos.
    """
    # Potencia RMS en ventana móvil de 100 ms
    n_win = int(0.10 * fs)
    energia = np.convolve(x_filtered ** 2, np.ones(n_win) / n_win, mode='same')
    rms_local = np.sqrt(np.maximum(energia, 0))

    # Umbral de detección (relativo al percentil 98 para evitar distorsión por clicks)
    rms_referencia = np.percentile(rms_local, 98)
    umbral = threshold_ratio * rms_referencia
    activo = (rms_local > umbral).astype(int)

    # Detectar transiciones de actividad
    cambios = np.diff(activo)
    inicios = np.where(cambios == 1)[0] + 1
    fines = np.where(cambios == -1)[0]

    if activo[0] == 1:
        inicios = np.insert(inicios, 0, 0)
    if activo[-1] == 1:
        fines = np.append(fines, len(activo) - 1)

    if len(inicios) > len(fines):
        inicios = inicios[:len(fines)]
    elif len(fines) > len(inicios):
        fines = fines[:len(inicios)]

    # Filtrar bloques por duración mínima y validación espectral
    duracion_minima_samples = int(duracion_minima_s * fs)
    bloques_validos = []
    
    for ini, fin in zip(inicios, fines):
        if (fin - ini) >= duracion_minima_samples:
            segmento = x_filtered[ini:fin]
            valida, snr = es_rafaga_afsk_valida(segmento, fs, snr_threshold=snr_threshold)
            if valida:
                bloques_validos.append((ini, fin, snr))
                
    return bloques_validos


def segmentar_audio_en_rafagas(fpath, output_dir=None, padding_s=1.0, duracion_minima_s=4.0, 
                               threshold_ratio=0.20, snr_threshold=10.0, use_grid=False, 
                               verbose=False, quiet=False, progreso=""):
    """
    Lee un archivo de audio WAV principal, localiza los bloques de ráfagas activas
    (con opción de optimización de umbral por grilla de búsqueda) y los exporta.
    """
    imprimir_progreso = not quiet
    imprimir_detalles = verbose and not quiet

    if imprimir_progreso:
        print(f"\n{progreso}Analizando: {os.path.basename(fpath)}")

    # 1. Cargar el audio original
    fs, data = wav.read(fpath)
    if data.ndim > 1:
        signal_mono = data[:, 0].astype(float)
    else:
        signal_mono = data.astype(float)
        
    x = signal_mono / np.max(np.abs(signal_mono) + 1e-12)
    nyq = fs / 2.0

    # 2. Filtrar en la banda útil de los tonos AFSK (1000 Hz a 2600 Hz)
    b, a = signal.butter(4, [1000.0 / nyq, 2600.0 / nyq], btype='bandpass')
    x_filtered = signal.lfilter(b, a, x)

    # 3. Optimización automática del umbral mediante grilla de búsqueda (si corresponde)
    final_threshold = threshold_ratio
    
    if use_grid:
        # Intentar detectar el baudrate esperado para saber cuántas ráfagas buscar
        n_esperado = 1
        try:
            from spectrum import AnalizadorEspectral
            from baud_detector import DetectorBaudios
            
            analizador = AnalizadorEspectral()
            res_espectral = analizador.analizar(x_filtered)
            f_mark = res_espectral.f_mark_hz
            f_space = res_espectral.f_space_hz
            
            detector = DetectorBaudios()
            baud_rate = detector.detectar(x_filtered, f_mark, f_space, res_espectral.segmento_inicio, res_espectral.segmento_fin)
            
            EXPECTED_BURSTS = {10: 1, 50: 2, 150: 2, 300: 2, 600: 1, 1200: 1}
            n_esperado = EXPECTED_BURSTS.get(baud_rate, 1)
            if imprimir_detalles:
                print(f"  • Baudrate detectado: {baud_rate} bd | Esperado: {n_esperado} ráfagas.")
        except Exception as e:
            if imprimir_detalles:
                print(f"  • [Grilla] Error detectando baudrate para {os.path.basename(fpath)}: {e}. Asumiendo 1 ráfaga.")
            n_esperado = 1

        # Candidatos de umbral para la grilla
        candidatos_umbral = np.arange(0.05, 0.55, 0.05)
        mejor_umbral = threshold_ratio
        mejor_distancia_esperada = 999
        mejor_snr_promedio = -1.0
        mejores_bloques = []

        for th in candidatos_umbral:
            bloques = detectar_bloques_activos(x_filtered, fs, th, duracion_minima_s, snr_threshold)
            n_detectado = len(bloques)
            
            # Buscar coincidencia exacta del número de ráfagas
            distancia = abs(n_detectado - n_esperado)
            snr_promedio = np.mean([b[2] for b in bloques]) if n_detectado > 0 else 0.0
            
            # Criterios de optimización:
            # 1. Minimizar la diferencia con el número esperado de ráfagas.
            # 2. Si hay empate, elegir el umbral con mayor SNR promedio de tonos.
            if distancia < mejor_distancia_esperada:
                mejor_distancia_esperada = distancia
                mejor_snr_promedio = snr_promedio
                mejor_umbral = th
                mejores_bloques = bloques
            elif distancia == mejor_distancia_esperada and snr_promedio > mejor_snr_promedio:
                mejor_snr_promedio = snr_promedio
                mejor_umbral = th
                mejores_bloques = bloques

        final_threshold = mejor_umbral
        bloques_validos = [(b[0], b[1]) for b in mejores_bloques]
        if imprimir_detalles:
            print(f"  • [Grilla] Umbral óptimo seleccionado: {final_threshold:.2f} (detectó {len(bloques_validos)} ráfagas).")
    else:
        # Detección simple con umbral fijo
        bloques = detectar_bloques_activos(x_filtered, fs, threshold_ratio, duracion_minima_s, snr_threshold)
        bloques_validos = [(b[0], b[1]) for b in bloques]

    if not bloques_validos:
        if imprimir_progreso:
            print(f"  ❌ No se detectaron ráfagas AFSK válidas en el archivo (Umbral: {final_threshold:.2f}).")
        return 0

    if imprimir_detalles:
        print(f"  ⚡ Se exportarán {len(bloques_validos)} ráfagas válidas:")

    # 4. Extraer y guardar cada ráfaga con padding
    padding_samples = int(padding_s * fs)
    basename = os.path.splitext(os.path.basename(fpath))[0]
    out_dir = output_dir if output_dir is not None else os.path.dirname(fpath)
    os.makedirs(out_dir, exist_ok=True)

    archivos_generados = 0
    for i, (ini, fin) in enumerate(bloques_validos):
        ini_padded = max(0, ini - padding_samples)
        fin_padded = min(len(data), fin + padding_samples)
        
        # Extraer del arreglo original (manteniendo tipo original)
        burst_samples = data[ini_padded:fin_padded]
        
        # Generar nombre del archivo de salida
        out_filename = f"{basename}_burst_{i + 1}.wav"
        out_path = os.path.join(out_dir, out_filename)
        
        # Guardar archivo de audio
        wav.write(out_path, fs, burst_samples)
        archivos_generados += 1

        # Si existe un archivo CSV de telemetría asociado al WAV original, copiarlo para la ráfaga
        csv_original = os.path.splitext(fpath)[0] + ".csv"
        if os.path.exists(csv_original):
            import shutil
            out_csv_path = os.path.join(out_dir, f"{basename}_burst_{i + 1}.csv")
            try:
                shutil.copy2(csv_original, out_csv_path)
            except Exception as e:
                if imprimir_detalles:
                    print(f"    ⚠️ No se pudo copiar la telemetría CSV: {e}")
        
        if imprimir_detalles:
            duracion_s = len(burst_samples) / fs
            print(f"    • Ráfaga {i+1}: {ini/fs:.2f}s a {fin/fs:.2f}s (Exportado: {out_filename}, Duración: {duracion_s:.2f}s)")

    return archivos_generados


def main():
    parser = argparse.ArgumentParser(description="Segmentador automático y adaptativo de ráfagas AFSK.")
    parser.add_argument("entrada", help="Archivo WAV continuo o carpeta que contiene grabaciones de audio.")
    parser.add_argument("-o", "--output-dir", default=None,
                        help="Directorio de destino para las ráfagas extraídas.")
    parser.add_argument("-p", "--padding", type=float, default=1.0,
                        help="Margen de seguridad (padding) en segundos a añadir al inicio y fin (por defecto: 1.0s).")
    parser.add_argument("-t", "--threshold", type=float, default=0.20,
                        help="Umbral de detección de energía RMS por defecto (por defecto: 0.20).")
    parser.add_argument("--snr-threshold", type=float, default=10.0,
                        help="Relación señal-ruido mínima espectral AFSK para validar tonos (por defecto: 10.0).")
    parser.add_argument("--min-duration", type=float, default=4.0,
                        help="Duración mínima en segundos para considerar un segmento activo (por defecto: 4.0s).")
    parser.add_argument("--grid", action="store_true",
                        help="Activar grilla de búsqueda automática para optimizar el umbral RMS por archivo.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Habilitar reportes detallados del proceso de segmentación y grilla.")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Deshabilitar toda impresión en consola (modo silencioso).")
    args = parser.parse_args()

    verbose = args.verbose
    quiet = args.quiet

    if os.path.isfile(args.entrada):
        segmentar_audio_en_rafagas(args.entrada, args.output_dir, args.padding, args.min_duration,
                                   args.threshold, args.snr_threshold, args.grid, verbose, quiet, progreso="[1/1] ")
    elif os.path.isdir(args.entrada):
        archivos = sorted(glob.glob(os.path.join(args.entrada, '**', '*.wav'), recursive=True))
        # Excluir archivos que ya están segmentados
        archivos_a_procesar = [f for f in archivos if "_burst_" not in os.path.basename(f)]
        
        if not archivos_a_procesar:
            if not quiet:
                print(f"No se encontraron archivos WAV principales para procesar en {args.entrada}")
            return
            
        if not quiet:
            print(f"Buscando grabaciones continuas en: {args.entrada}")
            print(f"Encontrados {len(archivos_a_procesar)} archivos principales.")
        
        total_generados = 0
        total_archivos = len(archivos_a_procesar)
        for idx, f in enumerate(archivos_a_procesar, 1):
            progreso = f"[{idx}/{total_archivos}] "
            num = segmentar_audio_en_rafagas(f, args.output_dir, args.padding, args.min_duration,
                                             args.threshold, args.snr_threshold, args.grid, verbose, quiet, progreso)
            total_generados += num
            
        if not quiet:
            print(f"\n==========================================================================")
            print(f" PROCESO COMPLETADO: {total_generados} ráfagas generadas en total.")
            print(f"==========================================================================")
    else:
        print(f"Error: la ruta de entrada '{args.entrada}' no existe.")


if __name__ == "__main__":
    main()
