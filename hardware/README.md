# 🛠️ Acondicionamiento Analógico y Hardware (Front-End)

El acoplamiento físico entre la Raspberry Pi Pico 2W y la radio analógica **Baofeng UV-82** se realiza de forma externa y no intrusiva a través del conector tipo Kenwood de 2 pines (*jack* de 3.5 mm para audio/parlante y *jack* de 2.5 mm para micrófono/PTT). 

Este directorio recopila las especificaciones de diseño, cálculos analógicos y diagramas esquemáticos para reproducir la interfaz física.

---

## 📌 Conector Kenwood y Distribución de Colores

Para evitar falsos contactos y ruidos analógicos inducidos por soldaduras deficientes, se utiliza un cable comercial premoldeado Kenwood cortado a la mitad. Los colores internos del conductor típicamente corresponden a las siguientes conexiones:

```
               [ PLUG 3.5 mm ]                     [ PLUG 2.5 mm ]
               (Parlante / RX)                     (Micrófono / TX)
               
                 .-.                                 .-.
                |   | Punta (Rojo): +Speaker        |   | Punta (Rojo): -Mic / PTT1
                |===|                               |===|
                |   | Anillo (Amarillo): Tx Data    |   | Anillo (Amarillo): +Mic
                |===|                               |===|
                |   | Base (Blanco): GND/Shield     |   | Base (Blanco): GND/PTT Base
                `---'                               `---'
```

---

## 📻 1. Circuito de Transmisión (Front-End TX) y Control PTT

El circuito transmisor acondiciona la señal digital de audio generada por PWM del microcontrolador y gobierna el pulsador *Push-To-Talk* (PTT) de la radio mediante aislamiento óptico.

### Diagrama Esquemático (ASCII)

```
                            Divisor Resistivo               Acople AC
                            (Atenuador tipo L)              Capacitor
                             
  [GP17 / Pin 22] ----------[ 10 kOhms (R1) ]-------+---------[ 47 uF (C1) ]---------> [Amarillo 2.5mm]
  (PWM Audio Out)                                   |             +                 (+Mic Radio)
                                             [ 1 kOhms (R2) ]
                                                    |
                                                  [GND]
                                                  
  [GP16 / Pin 21] -----[ 470 Ohms (R3) ]----+                  +------[ 1 kOhms ]---- [Rojo 3.5mm]
                                            |                  |                     (PTT2 Radio)
                                        (Pin 1)            (Pin 4)
                                        +-------+        +-------+
                                        | \ | / |  OPTO  | | / | |
                                        |  \ /  | PC817  |  /|   |
                                        |   V   |        |   v   |
                                        +-------+        +-------+
                                        (Pin 2)            (Pin 3)
                                            |                  |
  [GND / Pin 23] ---------------------------+                  +--------------------- [Blanco 2.5mm]
                                                                                     (GND/PTT Base)
```

### Explicación del Diseño y Cálculos
1. **Atenuación Resistiva (Divisor L):** La señal PWM sintetizada por el pin `GP17` oscila en un rango digital de 0 a 3.3 V pico a pico. Para no saturar el amplificador de entrada de micrófono de la radio (diseñado para niveles de voz de ~10-30 mV), el divisor resistivo ($R_1 = 10\text{ k}\Omega$, $R_2 = 1\text{ k}\Omega$) atenúa la señal en un factor de:
   $$Av = \frac{R_2}{R_1 + R_2} = \frac{1\text{ k}\Omega}{10\text{ k}\Omega + 1\text{ k}\Omega} \approx 0.091\text{ (i.e., } -20.8\text{ dB)}$$
   Esto reduce la señal a $\approx 300\text{ mV}_{\text{p-p}}$ en el nodo intermedio, previniendo recortes armónicos.
2. **Bloqueo de Tensión Continua (C1):** Un capacitor electrolítico de $47\,\mu\text{F}$ en serie bloquea la componente continua de la Pico 2W. Junto con la impedancia de entrada de la radio ($R_{\text{mic}} \approx 2\text{ k}\Omega$), forma un filtro paso alto con frecuencia de corte:
   $$f_c = \frac{1}{2\pi R_{\text{mic}} C_1} = \frac{1}{2\pi \cdot 2000\,\Omega \cdot 47\,\mu\text{F}} \approx 1.69\text{ Hz}$$
   Esto asegura una respuesta plana para las frecuencias de audio AFSK ($1200\text{ Hz}$ y $2400\text{ Hz}$).
3. **Aislamiento Galvánico del PTT:** Para transmitir, la radio requiere unir físicamente la línea de micrófono con masa. Para no cortocircuitar o introducir ruido del plano digital del microcontrolador al transmisor de RF, se implementa un optoacoplador **PC817**. El pin digital `GP16` enciende el LED interno (limitado por $R_3 = 470\,\Omega$), el cual satura el fototransistor interno para cerrar el circuito PTT de la radio de forma aislada.

---

## 🎧 2. Circuito de Recepción (Front-End RX)

El circuito adaptador del receptor reduce los altos niveles de tensión del altavoz analógico de la radio y los centra en el rango dinámico unipolar (0 a 3.3 V) de la entrada analógica `GP26 (ADC0)` del microcontrolador.

### Diagrama Esquemático (ASCII)

```
                  Divisor Resistivo             Acople AC        Red de **Offset** con *Bypass*
                  (Atenuador tipo L)           Capacitor          Divisor + *Bypass* C
                  
 [Rojo 3.5mm] ------[ 22 kOhms (R4) ]-------+---------[ 47 uF (C2) ]--------+--------- [ GP26 / ADC0 Pin 31 ]
 (Audio Speaker)                            |             +                 |
                                     [ 12 kOhms (R5) ]               [ 10 kOhms (R6) ] a 3.3V (Pin 36)
                                           |                                |
                                         [AGND]                             +-------+
                                                                            |       |
                                                                     [ 10 kOhms (R7) ] [ 100 nF (C3) ] (*Bypass*)
                                                                            |       |
                                                                          [AGND]  [AGND]
```

### Explicación del Diseño y Cálculos
1. **Atenuador de Entrada (R4, R5):** El volumen máximo de salida del altavoz de la radio puede superar los 5 V pico a pico, lo que dañaría la entrada del ADC. El divisor compuesto por $R_4 = 22\text{ k}\Omega$ y $R_5 = 12\text{ k}\Omega$ atenúa la señal analógica multiplicándola por un factor de $0.35$ ($\approx 1.76\text{ V}_{\text{p-p}}$ máximo), garantizando un margen seguro.
2. **Acoplamiento AC (C2):** Un capacitor electrolítico de $47\,\mu\text{F}$ en serie elimina el nivel de continua original de la etapa amplificadora de audio de la radio.
   * La resistencia de fuente equivalente es $R_s = R_4 \parallel R_5 \approx 7.76\text{ k}\Omega$.
   * La resistencia de polarización es $R_{\text{bias}} = R_6 \parallel R_7 = 5\text{ k}\Omega$.
   * La frecuencia de corte del filtro paso alto resultante es:
     $$f_c = \frac{1}{2\pi (R_s + R_{\text{bias}}) C_2} = \frac{1}{2\pi \cdot (7760\,\Omega + 5000\,\Omega) \cdot 47\,\mu\text{F}} \approx 0.265\text{ Hz}$$
     Esta frecuencia de corte garantiza que la señal analógica entre al ADC libre de distorsiones de fase temporales.
3. **Red de **Offset** (R6, R7):** El ADC de la Pico lee tensiones de $0$ a $3.3\text{ V}$. Para poder digitalizar el semiciclo negativo de la onda senoidal de audio sin recorte, el divisor resistivo simétrico de dos resistencias de $10\text{ k}\Omega$ inyecta un desplazamiento continuo de exactamente **$1.65\text{ V}$** (mitad del rango del ADC).
4. **Filtro de Ruido de Referencia (C3):** Un capacitor cerámico de $100\text{ nF}$ en paralelo con $R_7$ desacopla armónicos de alta frecuencia y ruidos de conmutación del bus digital de alimentación de 3.3 V, estabilizando la referencia analógica del ADC.

---

## ⚠️ Advertencia Crítica de Bucles de Tierra

> [!CAUTION]
> **COMPARTIR BATERÍA EXIGE MASA DE AUDIO AISLADA:**
> Si la Raspberry Pi Pico 2W y la radio Baofeng UV-82 se alimentan unificadamente de la misma batería (7.4 V de la radio adaptados a la Pico), ambos equipos ya poseen una referencia común a través de la masa de alimentación. 
> 
> En esta condición, **bajo ningún concepto se debe soldar el cable de masa del *jack* de 3.5 mm / 2.5 mm a la masa digital (GND) del microcontrolador**. Si se realiza esta conexión secundaria, se cierra un lazo inductivo que reduce la relación señal-ruido (SNR) del ADC e introduce un zumbido de clicks en el audio analógico, aumentando la tasa de errores de bit (BER).
