"""
generate_csv.py — Generador de CSV de BER a partir de la salida de run_suite.py
================================================================================
Proyecto : Comunicación Digital sobre Radios Analógicas FM (ORR - JAR 2026)
Instituto: Instituto de Automática (INAUT) — UNSJ — CONICET

Toma la salida de texto de run_suite.py (ya guardada en un archivo) y los
archivos CSV de telemetría GPS de los bursts, calcula la distancia real de cada
sesión de medición respecto al punto de referencia (primer burst cronológico), y
genera un CSV con el BER acumulado por distancia y velocidad de canal.

Uso:
    python3 generate_csv.py -i <salida.txt> -d <dir_bursts/> -o <resultado.csv>
    python3 generate_csv.py -i <salida.txt> -d <dir_bursts/> -o <resultado.csv> -t <umbral_m>

Argumentos:
    -i / --input      Archivo de texto con la salida de run_suite.py  [obligatorio]
    -d / --dir        Directorio con los _burst_*.csv de telemetría   [obligatorio]
    -o / --output     Archivo CSV de salida                           [obligatorio]
    -t / --threshold  Umbral en metros para detectar cambio de sesión [opcional]
                      Si se omite, se usa detección automática por saltos estadísticos.
================================================================================
"""

import argparse
import csv
import math
import os
import re
import sys
from datetime import datetime, timezone


# ─────────────────────────────────────────────────────────────────────────────
# Constantes del dominio
# ─────────────────────────────────────────────────────────────────────────────

BAUDRATES_ESPERADOS = [10, 50, 150, 300, 600, 1200]

BITS_POR_BAUDRATE = {
    10:   127,
    50:   1270,
    150:  3175,
    300:  6350,
    600:  12700,
    1200: 12700,
}


# ─────────────────────────────────────────────────────────────────────────────
# Funciones auxiliares de GPS
# ─────────────────────────────────────────────────────────────────────────────

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia geodésica en metros entre dos coordenadas WGS-84."""
    R = 6_371_000.0  # radio medio de la Tierra en metros
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def parse_telemetry_csv(csv_path: str) -> dict | None:
    """
    Lee un archivo CSV de telemetría de burst y extrae timestamp, lat y lon.
    Retorna None si el archivo no tiene los campos necesarios.
    """
    datos = {}
    try:
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    clave = row[0].strip()
                    valor = row[1].strip()
                    datos[clave] = valor
    except Exception as e:
        print(f"  ⚠️  No se pudo leer {csv_path}: {e}", file=sys.stderr)
        return None

    campos_requeridos = ['Timestamp_GPS_UTC', 'Latitud', 'Longitud']
    for campo in campos_requeridos:
        if campo not in datos:
            print(f"  ⚠️  Campo '{campo}' faltante en {csv_path}", file=sys.stderr)
            return None

    try:
        ts_str = datos['Timestamp_GPS_UTC']
        # Normalizar: reemplazar Z final por +00:00 para fromisoformat
        ts_str = ts_str.replace('Z', '+00:00')
        timestamp = datetime.fromisoformat(ts_str)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        lat = float(datos['Latitud'])
        lon = float(datos['Longitud'])
    except (ValueError, KeyError) as e:
        print(f"  ⚠️  Error parseando campos numéricos en {csv_path}: {e}", file=sys.stderr)
        return None

    return {'timestamp': timestamp, 'lat': lat, 'lon': lon}


# ─────────────────────────────────────────────────────────────────────────────
# Carga y agrupamiento de bursts por sesión de distancia
# ─────────────────────────────────────────────────────────────────────────────

def cargar_metadatos_bursts(bursts_dir: str) -> list[dict]:
    """
    Lee todos los _burst_*.csv del directorio e infiere el alias (nombre sin extensión).
    Retorna lista de dicts ordenada cronológicamente por timestamp GPS.
    """
    bursts = []
    for nombre in sorted(os.listdir(bursts_dir)):
        if not nombre.endswith('.csv'):
            continue
        # Solo procesar archivos de ráfaga (con _burst_ en el nombre)
        if '_burst_' not in nombre:
            continue
        alias = nombre[:-4]  # quitar .csv
        ruta_csv = os.path.join(bursts_dir, nombre)
        meta = parse_telemetry_csv(ruta_csv)
        if meta is None:
            continue
        bursts.append({
            'alias': alias,
            'timestamp': meta['timestamp'],
            'lat': meta['lat'],
            'lon': meta['lon'],
        })

    if not bursts:
        print("Error: No se encontraron archivos _burst_*.csv en el directorio especificado.", file=sys.stderr)
        sys.exit(1)

    # Ordenar cronológicamente
    bursts.sort(key=lambda b: b['timestamp'])

    # Calcular distancia respecto al primer burst (punto de referencia)
    ref_lat = bursts[0]['lat']
    ref_lon = bursts[0]['lon']
    for b in bursts:
        b['dist_ref_m'] = haversine(ref_lat, ref_lon, b['lat'], b['lon'])

    return bursts


def detectar_umbral_automatico(bursts: list[dict]) -> float:
    """
    Calcula automáticamente el umbral de cambio de sesión como:
        media + 2 × desviación estándar
    de los saltos de distancia entre bursts consecutivos.
    """
    if len(bursts) < 2:
        return 50.0  # valor mínimo razonable si hay muy pocos bursts

    saltos = []
    for i in range(1, len(bursts)):
        salto = abs(bursts[i]['dist_ref_m'] - bursts[i - 1]['dist_ref_m'])
        saltos.append(salto)

    media = sum(saltos) / len(saltos)
    varianza = sum((s - media) ** 2 for s in saltos) / len(saltos)
    desv = math.sqrt(varianza)
    umbral = media + 2 * desv

    print(f"  → Umbral automático detectado: {umbral:.1f} m "
          f"(media saltos={media:.1f} m, σ={desv:.1f} m)")
    return max(umbral, 10.0)  # mínimo 10 m para evitar ruido GPS


def agrupar_en_sesiones(bursts: list[dict], threshold: float | None) -> list[dict]:
    """
    Agrupa los bursts en sesiones de distancia.
    Retorna lista de sesiones: [{distancia_m, aliases}]
    """
    if threshold is None:
        threshold = detectar_umbral_automatico(bursts)
    else:
        print(f"  → Umbral de sesión: {threshold:.1f} m (provisto por usuario)")

    sesiones = []
    sesion_actual = [bursts[0]]

    for i in range(1, len(bursts)):
        salto = abs(bursts[i]['dist_ref_m'] - bursts[i - 1]['dist_ref_m'])
        if salto > threshold:
            # Cerrar sesión actual
            sesiones.append(sesion_actual)
            sesion_actual = [bursts[i]]
        else:
            sesion_actual.append(bursts[i])

    sesiones.append(sesion_actual)  # cerrar última sesión

    # Calcular distancia representativa de cada sesión (promedio de sus bursts)
    resultado = []
    for grupo in sesiones:
        dist_promedio = sum(b['dist_ref_m'] for b in grupo) / len(grupo)
        aliases = [b['alias'] for b in grupo]
        resultado.append({
            'distancia_m': round(dist_promedio),
            'aliases': set(aliases),
        })

    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# Parseo de la salida de run_suite.py
# ─────────────────────────────────────────────────────────────────────────────

def parsear_salida_run_suite(texto: str) -> list[dict]:
    """
    Extrae los resultados del bloque RESUMEN de la salida de run_suite.py.

    Formato esperado de cada línea del resumen:
        audio_sdr_..._burst_1   | 50      | 9.3701   | 119      | 0.010/0.00200 | 0.9349

    También intenta extraer total_bits del campo Errores en la salida por línea:
        [2/35] Procesando: audio_sdr_..._burst_1... ... | Errores: 119/1270 | ...
    """
    resultados = {}

    # Paso 1: extraer errores/total_bits de la salida de progreso línea a línea
    patron_progreso = re.compile(
        r'Procesando:\s+(?P<alias>\S+)\.\.\.'
        r'.*?Errores:\s+(?P<errores>\d+)/(?P<total_bits>\d+)',
        re.DOTALL
    )
    # Línea de progreso está en una sola línea
    patron_progreso_linea = re.compile(
        r'Procesando:\s+(?P<alias>[^\s.]+)\.\.\..*?Errores:\s+(?P<errores>\d+)/(?P<total_bits>\d+)'
    )
    for m in patron_progreso_linea.finditer(texto):
        alias = m.group('alias')
        resultados[alias] = {
            'alias': alias,
            'errores': int(m.group('errores')),
            'total_bits': int(m.group('total_bits')),
            'baudrate': None,
        }

    # Paso 2: extraer baudrate del bloque RESUMEN (tabla final)
    # Línea del resumen: "alias   | baudios | ber | errores | kp/ki | confianza"
    patron_resumen = re.compile(
        r'^(?P<alias>audio_sdr_\S+)\s*\|\s*(?P<baudrate>\d+)\s*\|',
        re.MULTILINE
    )
    for m in patron_resumen.finditer(texto):
        alias = m.group('alias').strip()
        baudrate = int(m.group('baudrate'))
        if alias in resultados:
            resultados[alias]['baudrate'] = baudrate
        else:
            # Si no se encontró en la salida de progreso, inferir total_bits por baudrate
            bits = BITS_POR_BAUDRATE.get(baudrate, 127)
            # Intentar extraer errores del resumen
            resultados[alias] = {
                'alias': alias,
                'baudrate': baudrate,
                'errores': None,
                'total_bits': bits,
            }

    # Paso 3: para filas del resumen que no tienen errores aún, extraerlos del resumen
    patron_resumen_completo = re.compile(
        r'^(?P<alias>audio_sdr_\S+)\s*\|\s*(?P<baudrate>\d+)\s*\|\s*[\d.]+\s*\|\s*(?P<errores>\d+)\s*\|',
        re.MULTILINE
    )
    for m in patron_resumen_completo.finditer(texto):
        alias = m.group('alias').strip()
        baudrate = int(m.group('baudrate'))
        errores = int(m.group('errores'))
        if alias in resultados:
            if resultados[alias]['errores'] is None:
                resultados[alias]['errores'] = errores
            if resultados[alias]['baudrate'] is None:
                resultados[alias]['baudrate'] = baudrate
        else:
            bits = BITS_POR_BAUDRATE.get(baudrate, 127)
            resultados[alias] = {
                'alias': alias,
                'baudrate': baudrate,
                'errores': errores,
                'total_bits': bits,
            }

    # Filtrar entradas incompletas
    validos = []
    for alias, r in resultados.items():
        if r['baudrate'] is None:
            print(f"  ⚠️  Sin baudrate para '{alias}', se omite.", file=sys.stderr)
            continue
        if r['errores'] is None:
            print(f"  ⚠️  Sin errores para '{alias}', se omite.", file=sys.stderr)
            continue
        validos.append(r)

    return validos


# ─────────────────────────────────────────────────────────────────────────────
# Cálculo de BER acumulado
# ─────────────────────────────────────────────────────────────────────────────

def calcular_tabla_ber(sesiones: list[dict], resultados: list[dict]) -> dict:
    """
    Cruza cada resultado (alias) con su sesión y acumula errores y bits
    por (distancia, baudrate). Calcula BER = Σerrores / Σbits × 100.

    Retorna: {distancia_m: {baudrate: ber_pct}}
    """
    # Índice alias → sesión
    alias_a_sesion = {}
    for sesion in sesiones:
        for alias in sesion['aliases']:
            alias_a_sesion[alias] = sesion['distancia_m']

    # Acumuladores: {distancia_m: {baudrate: [errores, bits]}}
    acum = {}
    for r in resultados:
        alias = r['alias']
        dist = alias_a_sesion.get(alias)
        if dist is None:
            print(f"  ⚠️  Alias '{alias}' no encontrado en ninguna sesión GPS, se omite.",
                  file=sys.stderr)
            continue
        baud = r['baudrate']
        if dist not in acum:
            acum[dist] = {}
        if baud not in acum[dist]:
            acum[dist][baud] = [0, 0]
        acum[dist][baud][0] += r['errores']
        acum[dist][baud][1] += r['total_bits']

    # Calcular BER
    tabla = {}
    for dist, baudrates in acum.items():
        tabla[dist] = {}
        for baud, (err, bits) in baudrates.items():
            if bits > 0:
                tabla[dist][baud] = (err / bits) * 100.0
            else:
                tabla[dist][baud] = None

    return tabla


# ─────────────────────────────────────────────────────────────────────────────
# Escritura del CSV de salida
# ─────────────────────────────────────────────────────────────────────────────

def escribir_csv(tabla: dict, output_path: str):
    """
    Escribe el CSV con estructura:
        Distancia_m, 10, 50, 150, 300, 600, 1200
        <dist>,      ber, ber, ...
    """
    distancias = sorted(tabla.keys())
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Cabecera
        writer.writerow(['Distancia_m'] + BAUDRATES_ESPERADOS)
        # Filas
        for dist in distancias:
            fila = [dist]
            for baud in BAUDRATES_ESPERADOS:
                ber = tabla[dist].get(baud)
                if ber is not None:
                    fila.append(f"{ber:.2f}")
                else:
                    fila.append('')
            writer.writerow(fila)
    print(f"\n✅ CSV generado: {output_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog='generate_csv.py',
        description='Genera un CSV de BER por distancia y baudrate a partir de la salida de run_suite.py.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplo de uso:\n"
            "  python3 generate_csv.py -i salida.txt -d data_generated/libre/ -o resultado.csv\n"
            "  python3 generate_csv.py -i salida.txt -d data_generated/campo/ -o campo.csv -t 200\n\n"
            "Flujo recomendado:\n"
            "  1. python3 ORR/processing/run_suite.py <dir_bursts/> > salida.txt\n"
            "  2. python3 ORR/processing/generate_csv.py -i salida.txt -d <dir_bursts/> -o resultado.csv"
        )
    )

    parser.add_argument(
        '-i', '--input',
        metavar='ARCHIVO',
        help='Archivo de texto con la salida de run_suite.py'
    )
    parser.add_argument(
        '-d', '--dir',
        metavar='DIRECTORIO',
        help='Directorio con los _burst_*.csv de telemetría GPS'
    )
    parser.add_argument(
        '-o', '--output',
        metavar='SALIDA',
        help='Archivo CSV de salida'
    )
    parser.add_argument(
        '-t', '--threshold',
        metavar='METROS',
        type=float,
        default=None,
        help='Umbral en metros para detectar cambio de sesión de distancia. '
             'Si se omite, se calcula automáticamente.'
    )

    args = parser.parse_args()

    # Validar argumentos obligatorios manualmente para dar error descriptivo
    faltantes = []
    if not args.input:
        faltantes.append('-i / --input')
    if not args.dir:
        faltantes.append('-d / --dir')
    if not args.output:
        faltantes.append('-o / --output')

    if faltantes:
        print(f"\nError: Los siguientes argumentos son obligatorios: {', '.join(faltantes)}", file=sys.stderr)
        print("\nUso correcto:", file=sys.stderr)
        print("  python3 generate_csv.py -i <salida.txt> -d <dir_bursts/> -o <resultado.csv>", file=sys.stderr)
        print("\nEjemplo:", file=sys.stderr)
        print("  python3 generate_csv.py -i salida_libre.txt -d data_generated/libre/ -o libre_resultado.csv", file=sys.stderr)
        sys.exit(1)

    # Validar existencia de archivos y directorios
    if not os.path.isfile(args.input):
        print(f"\nError: El archivo de entrada '{args.input}' no existe.", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(args.dir):
        print(f"\nError: El directorio '{args.dir}' no existe.", file=sys.stderr)
        sys.exit(1)

    # ── Paso 1: Leer salida de run_suite.py ──────────────────────────────────
    print(f"\n[1/4] Leyendo salida de run_suite.py desde '{args.input}'...")
    with open(args.input, 'r', encoding='utf-8') as f:
        texto = f.read()

    resultados = parsear_salida_run_suite(texto)
    if not resultados:
        print("Error: No se encontraron resultados válidos en el archivo de entrada.", file=sys.stderr)
        print("Verifique que el archivo contenga la salida completa de run_suite.py.", file=sys.stderr)
        sys.exit(1)
    print(f"  → {len(resultados)} bursts encontrados en la salida.")

    # ── Paso 2: Cargar metadatos GPS y agrupar sesiones ──────────────────────
    print(f"\n[2/4] Leyendo telemetría GPS desde '{args.dir}'...")
    bursts = cargar_metadatos_bursts(args.dir)
    print(f"  → {len(bursts)} bursts con GPS cargados.")
    print(f"  → Punto de referencia: lat={bursts[0]['lat']:.7f}, lon={bursts[0]['lon']:.7f} "
          f"({bursts[0]['timestamp'].strftime('%Y-%m-%dT%H:%M:%S')} UTC)")

    print(f"\n[3/4] Detectando sesiones de distancia...")
    sesiones = agrupar_en_sesiones(bursts, args.threshold)
    print(f"  → {len(sesiones)} sesiones detectadas:")
    for s in sesiones:
        print(f"     • {s['distancia_m']} m  →  {len(s['aliases'])} bursts")

    # ── Paso 3: Calcular BER acumulado ───────────────────────────────────────
    print(f"\n[4/4] Calculando BER acumulado por sesión y baudrate...")
    tabla = calcular_tabla_ber(sesiones, resultados)

    # Mostrar tabla en consola
    encabezado = f"{'Distancia_m':>12} | " + " | ".join(f"{b:>6}" for b in BAUDRATES_ESPERADOS)
    print(f"\n  {encabezado}")
    print(f"  {'-' * len(encabezado)}")
    for dist in sorted(tabla.keys()):
        fila = f"  {dist:>12} | "
        celdas = []
        for baud in BAUDRATES_ESPERADOS:
            ber = tabla[dist].get(baud)
            celdas.append(f"{ber:>6.2f}" if ber is not None else f"{'N/A':>6}")
        fila += " | ".join(celdas)
        print(fila)

    # ── Paso 4: Escribir CSV ─────────────────────────────────────────────────
    escribir_csv(tabla, args.output)


if __name__ == '__main__':
    main()
