"""
lfsr.py — Generador de Secuencia Pseudoaleatoria PRBS-7 mediante LFSR
============================================================================
Proyecto : Comunicación Digital sobre Radios Analógicas FM (JAR 2026)
Instituto: Instituto de Automática (INAUT) — UNSJ — CONICET

Implementa un Registro de Desplazamiento con Retroalimentación Lineal
(LFSR — Linear Feedback Shift Register) basado en el polinomio
característico de Golomb (1982):

    Polinomio generador:  x^7 + x^6 + 1
    Recurrencia:          y(n) = y(n-6) ⊕ y(n-7)
    Ciclo maximal:        2^7 - 1 = 127 bits

La secuencia PRBS-7 resultante posee las siguientes propiedades
que la hacen ideal para la caracterización de la Capa Física:

  1. Espectro plano: aproxima ruido blanco en el ancho de banda del canal.
  2. Autocorrelación impulsiva: permite sincronismo y detección de errores.
  3. Contiene rachas de hasta 7 bits idénticos consecutivos, estresando
     al máximo la recuperación de reloj del demodulador.
  4. Exactamente 64 unos y 63 ceros: balance estadístico casi perfecto.

Referencia:
    Golomb, S. W. (1982). Shift Register Sequences.
    Aegean Park Press. ISBN 0-89412-048-4.
============================================================================
"""


class LFSR:
    """
    Registro de Desplazamiento con Retroalimentación Lineal (LFSR)
    de 7 bits para generación de secuencias pseudoaleatorias PRBS-7.

    Arquitectura: Fibonacci (retroalimentación externa).
    Desplazamiento: hacia la derecha (LSB → salida).
    Retroalimentación: XOR de los bits en las posiciones 7 y 6 (1-indexed),
                       inyectado en la posición más significativa (bit 6, 0-indexed).

    Ejemplo de operación (3 pasos desde seed 0x7F = 1111111):

        Paso 0: reg = 1111111, salida = 1, feedback = 1⊕1 = 0 → 0111111
        Paso 1: reg = 0111111, salida = 1, feedback = 0⊕1 = 1 → 1011111
        Paso 2: reg = 1011111, salida = 1, feedback = 1⊕0 = 1 → 1101111
        ...
    """

    SEQUENCE_LENGTH = 127   # 2^7 - 1 (ciclo maximal)
    REGISTER_WIDTH  = 7     # Ancho del registro en bits

    def __init__(self, seed=0x7F):
        """
        Inicializa el LFSR con un estado semilla.

        Args:
            seed (int): Estado inicial del registro de 7 bits.
                        Rango válido: 1 a 127 (0x01 a 0x7F).
                        El estado 0 es prohibido (punto fijo del LFSR,
                        no genera secuencia alguna).
                        Valor por defecto: 0x7F (todos los bits en 1).
        """
        if not (1 <= seed <= 0x7F):
            raise ValueError(
                "Seed LFSR fuera de rango: debe ser 1 <= seed <= 127 (0x7F). "
                "El estado 0x00 es un punto fijo prohibido del LFSR."
            )
        self._seed = seed
        self._register = seed

    def _step(self):
        """
        Ejecuta un ciclo de reloj del LFSR.

        Operación:
            1. Extrae el bit de salida (LSB del registro).
            2. Calcula el bit de retroalimentación:
               feedback = bit[6] ⊕ bit[5]  (0-indexed)
                        = y(n-7) ⊕ y(n-6)  (notación de Golomb)
            3. Desplaza el registro una posición a la derecha.
            4. Inserta el bit de feedback en la posición más significativa.

        Returns:
            int: Bit de salida (0 o 1).
        """
        # Bit de salida: LSB
        output_bit = self._register & 1

        # Retroalimentación: XOR de taps en posiciones 7 y 6 (1-indexed)
        # Al desplazar a la derecha, la Etapa 7 es el Bit 0 y la Etapa 6 es el Bit 1.
        feedback = (self._register ^ (self._register >> 1)) & 1

        # Desplazamiento a la derecha + inserción del feedback en MSB
        self._register = (self._register >> 1) | (feedback << 6)

        return output_bit

    def generate_sequence(self):
        """
        Genera un ciclo completo de la secuencia PRBS-7 (127 bits).

        Reinicia el registro al estado semilla antes de generar,
        garantizando reproducibilidad determinista.

        Returns:
            list[int]: Lista de 127 elementos, cada uno 0 o 1.

        Propiedades verificables del resultado:
            - len(secuencia) == 127
            - sum(secuencia) == 64  (exactamente 64 unos)
            - 127 - sum(secuencia) == 63  (exactamente 63 ceros)
        """
        self._register = self._seed
        return [self._step() for _ in range(self.SEQUENCE_LENGTH)]

    def reset(self):
        """Reinicia el registro al estado semilla original."""
        self._register = self._seed

    @property
    def state(self):
        """Estado actual del registro (lectura, para diagnóstico)."""
        return self._register
