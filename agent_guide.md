# Guía de Operación y Procesamiento para Agentes Futuros (ORR)

Esta guía explica el diseño experimental del sistema **Outdoor Radio Robotics (ORR)**, la estructura de los archivos de audio de medición, y el procedimiento exacto para procesar el dataset sin modificar el software del repositorio.

---

## 📻 1. Contexto del Ensayo de Campo

El sistema ORR utiliza transceptores analógicos FM (Baofeng UV-82) acoplados a microcontroladores Raspberry Pi Pico 2W. La transmisión digital se realiza usando modulación **AFSK** (1200 Hz para *Mark*/1, 2400 Hz para *Space*/0) a velocidades de 10, 50, 150, 300, 600, y 1200 baudios.

### Generación y Grabación de los Audios
1. **Transmisor (`firmware/tx`):**
   - Transmite secuencias de datos pseudoaleatorios PRBS-7 de 127 bits.
   - Para evitar dañar térmicamente el paso final de potencia RF de la radio (límite estricto de 30s de transmisión continua), las transmisiones largas se **fragmentan en ráfagas (bursts)** separadas por intervalos de enfriamiento (cooldown).
   - *10 bd:* 1 ráfaga de 127 bits (~12.7s + pre/post delay).
   - *50 bd:* 2 ráfagas de 1270 bits cada una, con 27s de enfriamiento en el medio.
   - *150 bd:* 2 ráfagas de 3175 bits cada una, con 23s de enfriamiento.
   - *300 bd:* 2 ráfagas de 6350 bits cada una, con 23s de enfriamiento.
   - *600 bd:* 1 ráfaga de 12700 bits (~21s + pre/post delay).
   - *1200 bd:* 1 ráfaga de 12700 bits (~10.5s + pre/post delay).

2. **Receptor (`firmware/rx`):**
   - El receptor corre una interfaz Web-DAQ en el navegador móvil del operador.
   - Graba de forma **continua** todo el audio de la sesión (incluidos silencios, ruido de squelch, y múltiples ráfagas) y genera un único archivo `.wav` principal (ej. `audio_sdr_20260604_172447.wav`).

---

## 🎧 2. Archivos de Ráfagas (`_burst_X.wav`) vs. Archivos Principales

Dado que la grabación es continua, el archivo `.wav` principal contiene el ruido de fondo, silencios de cooldown, y todas las ráfagas transmitidas en la sesión.

- **`audio_sdr_*.wav` (Principal con ráfagas asociadas):** Contiene la sesión completa. Si intentamos procesar este archivo con la suite de demodulación, el analizador espectral detectará y se centrará únicamente en la *primera ráfaga*, ignorando las siguientes y duplicando el análisis de la primera ráfaga.
- **`audio_sdr_*_burst_X.wav` (Ráfagas individuales):** Son segmentos de audio pre-extraídos que contienen estrictamente la ráfaga `X` de la sesión. Estos deben procesarse individualmente para evaluar el desempeño (BER y Confianza) de cada ráfaga de forma aislada.
- **`audio_sdr_*.wav` (Principal SIN ráfagas asociadas):** Sesiones de transmisión que constan de una única ráfaga (como a 10 bd o 1200 bd), donde no se requería fragmentación o no se extrajeron ráfagas separadas. Estos archivos principales deben ser procesados directamente.

---

## ⚡ 3. Procedimiento de Filtrado y Ejecución Paso a Paso

Para procesar el dataset respetando la lógica descrita y sin alterar el código del repositorio, se utiliza una técnica de filtrado por directorios temporales:

### Paso A: Crear un directorio de entrada filtrado
Creamos un directorio temporal `data_filtered` y copiamos únicamente los archivos requeridos:
1. Copiar todos los archivos que contengan `_burst_` en su nombre (junto con sus metadatos `.csv`).
2. Copiar los archivos `.wav` y `.csv` principales que **no tengan** ningún archivo de ráfaga asociado en el directorio original.

Ejemplo en Bash para procesar la distancia de `5` metros:
```bash
# Limpiar y preparar carpeta temporal
mkdir -p data_filtered/5

# 1. Copiar todos los archivos de ráfaga (wav y csv correspondientes)
cp data/libre/5/*_burst_*.wav data_filtered/5/
for f in data_filtered/5/*_burst_*.wav; do
    # Obtener el nombre base del csv de metadatos (el csv original se llama igual que el wav principal)
    base=$(echo $(basename $f) | sed 's/_burst_.*//')
    cp data/libre/5/${base}.csv data_filtered/5/$(basename $f .wav).csv
done

# 2. Copiar los archivos principales que no tienen ráfagas
for f in data/libre/5/audio_sdr_*.wav; do
    if [[ ! "$f" =~ _burst_ ]]; then
        base=$(basename $f .wav)
        # Si no existe ningún archivo de ráfaga para este base, copiar el principal
        if ! ls data/libre/5/${base}_burst_* 1>/dev/null 2>&1; then
            cp data/libre/5/${base}.wav data_filtered/5/
            cp data/libre/5/${base}.csv data_filtered/5/
        fi
    fi
done
```

### Paso B: Ejecutar la Suite de Demodulación
Una vez preparada la carpeta temporal con los archivos de entrada correctos, se ejecuta la suite original de procesamiento:
```bash
python3 ORR/processing/run_suite.py data_filtered/5
```

Este procedimiento garantiza que la suite de demodulación se ejecute sobre los archivos correctos sin duplicar datos y procesando todas las ráfagas individuales disponibles.
