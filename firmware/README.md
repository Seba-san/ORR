# 💾 Firmware Embebido: Módem AFSK para Raspberry Pi Pico 2W

Esta carpeta contiene el firmware en **MicroPython** desarrollado para los nodos Transmisor (TX) y Receptor (RX) del sistema de comunicación digital ORR, ejecutados en microcontroladores Raspberry Pi Pico 2W (basados en el chip RP2350).

---

## 🛠️ Requisitos Previos e Instalación

### 1. Cargar MicroPython
Ambos microcontroladores deben tener instalado **MicroPython v1.20** o superior.
1. Descarga el firmware oficial `.uf2` para la Raspberry Pi Pico 2W/W desde [micropython.org](https://micropython.org/download/RPI_PICO2W/).
2. Conecta la placa a la computadora por USB manteniendo presionado el botón **BOOTSEL**.
3. Suelta el botón una vez que la placa aparezca como una unidad de almacenamiento masivo llamada `RPI-RP2` (o similar).
4. Arrastra y suelta el archivo `.uf2` dentro de la unidad. El dispositivo se reiniciará automáticamente corriendo MicroPython.

### 2. Cargar los Archivos
Utiliza un IDE compatible como **Thonny** o herramientas de línea de comandos como `mpremote` para transferir los archivos:
* **Para el Transmisor:** Carga todos los archivos de la carpeta [tx/](./tx) en la raíz de la memoria flash del microcontrolador.
* **Para el Receptor:** Carga todos los archivos de la carpeta [rx/](./rx) en la raíz de la memoria flash del microcontrolador.

---

## 📌 Mapeo de Pines de la Raspberry Pi Pico 2W

Las interfaces se han estandarizado sobre las siguientes conexiones físicas de la placa:

| Pin Físico | Pin Lógico | Función en el Sistema | Conexión Externa Asociada |
| :---: | :---: | :--- | :--- |
| **Pin 4** | `GP2` | Entrada Digital (Pulsador) | Pulsador de activación (Gatillo) a tierra (`GND`) |
| **Pin 22** | `GP17` | Salida de Audio PWM (TX) | Entrada al Atenuador analógico de Transmisión (Mic) |
| **Pin 21** | `GP16` | Control Digital PTT | Entrada del Optoacoplador PC817 (Pin 1 - Ánodo) |
| **Pin 23** | `GND` | Tierra Digital | Entrada del Optoacoplador PC817 (Pin 2 - Cátodo) |
| **Pin 31** | `GP26` | Entrada de Adquisición ADC (RX) | Salida del circuito Front-End Analógico (AFE) |
| **Pin 33** | `AGND` | Tierra Analógica | Referencia del circuito Front-End Analógico (AFE) |
| **Pin 36** | `3V3_OUT` | Alimentación de Referencia | Red de polarización resistiva del Front-End (Offset) |

> [!WARNING]
> **PREVENCIÓN DE BUCLES DE TIERRA:**
> Al compartir la alimentación directa de la batería del transceptor, el microcontrolador y la radio poseen una referencia de masa común. Por lo tanto, **bajo ningún concepto se debe conectar el pin de masa (GND) del conector *jack* de audio a la masa digital de la placa Pico 2W**. De realizar esta conexión secundaria, se creará un bucle de tierra cerrado inductivo que inyectará zumbidos electromagnéticos en el receptor, aumentando la tasa de errores de bit y pudiendo ocasionar daños físicos por corrientes de retorno de RF.

---

## 🚀 Instrucciones de Operación

### 1. Transmisor (TX)
El firmware del transmisor sintetiza tonos AFSK puros mediante el periférico PWM por hardware a 125 kHz utilizando una tabla de búsqueda senoidal de 256 muestras precomputada para anular la latencia y fluctuaciones temporales (*jitter*) inducidas por el recolector de basura de MicroPython.

* Al alimentar el nodo TX, este ingresa en modo de espera.
* Al presionar el botón físico en `GP2` (Gatillo), el transmisor inicia una ráfaga:
  1. Activa el pin `GP16` para cerrar el circuito PTT a través del optoacoplador, encendiendo la transmisión de la radio.
  2. Genera una portadora en vacío durante un retardo de preámbulo configurable para compensar la latencia de apertura del circuito silenciador (*squelch*) del receptor.
  3. Sintetiza y transmite cíclicamente el patrón pseudoaleatorio de bits **PRBS-7** generado por el registro de desplazamiento con retroalimentación lineal ($y(n) = y(n-6) \oplus y(n-7)$). El volumen de datos se adapta automáticamente a la velocidad configurada.
  4. Finaliza con un retardo de cola y apaga el pin `GP16` (PTT) para retornar al modo de escucha.
  5. **Protección Térmica:** La máquina de estados bloquea el gatillo y obliga a un periodo de enfriamiento ininterrumpido igual al 100% de la duración de la transmisión para proteger el amplificador final de RF de la radio Baofeng.

### 2. Receptor (RX) y Interfaz Web-DAQ
El receptor actúa como un digitalizador analógico inalámbrico.
* Al encender el receptor, este levanta un **Punto de Acceso Wi-Fi** local con las siguientes credenciales:
  * **SSID:** `PicoSDR`
  * **Contraseña:** `sdrpassword`
  * **IP del Servidor:** `192.168.4.1`
* El operador de campo se conecta a esta red con su teléfono inteligente y accede a la dirección web `http://192.168.4.1` en su navegador.
* La interfaz de control **Web-DAQ** (ejecutada mediante JavaScript en el navegador del cliente) realiza las siguientes tareas de forma asíncrona:
  1. Se conecta al endpoint `/stream` del *socket* TCP de la Pico.
  2. En Core 1 de la Pico, las interrupciones del Timer leen el ADC GP26 a una tasa constante de **19.2 kHz** y depositan los datos en un esquema de doble *buffer* (*ping-pong*) de 19,200 muestras firmadas de 16 bits.
  3. En Core 0 de la Pico, el servidor web realiza un *streaming* binario continuo de estos bloques hacia el celular.
  4. El script en JavaScript almacena los bloques en RAM y graba concurrentemente los metadatos de posicionamiento GPS del celular en tiempo real.
  5. Al pulsar "Detener", el navegador concatena los bloques de audio, les inyecta una **cabecera estándar RIFF/WAVE de 44 bytes** y genera la descarga de un archivo `.wav` sin comprimir (19200 Hz, Mono, 16-bit signed) y un archivo de telemetría `.csv` indexado con la ubicación exacta del ensayo.
