"""
modulator.py — Modulador CPFSK (Phase Continuous Frequency Shift Keying) con Watchdog Térmico
============================================================================
Proyecto : Comunicación Digital sobre Radios Analógicas FM (JAR 2026)
Instituto: Instituto de Automática (INAUT) — UNSJ — CONICET
Hardware : Raspberry Pi Pico 2W (RP2350) + Baofeng UV-82

Módulo de modulación digital optimizado para MicroPython (RP2350).
Implementa un lazo crítico libre de asignaciones de memoria en el heap (Zero-Allocation),
con un watchdog térmico integrado de seguridad que corta la transmisión
inmediatamente si supera el límite máximo estricto de segundos.
============================================================================
"""

import math
import time
import gc
import config

class AFSKModulator:
    """
    Modulador digital AFSK de fase continua (CPFSK) optimizado con Watchdog térmico.
    """

    def __init__(self, table_size=256):
        """
        Inicializa el modulador y precomputa la tabla senoidal de alta resolución.
        
        Args:
            table_size (int): Cantidad de muestras en la tabla de onda.
                              Debe ser potencia de 2 para optimizar el acceso por máscara de bits.
        """
        self.table_size = table_size
        
        # Sintetizamos la tabla de onda senoidal de 16 bits (rango 0 a 65534).
        # Esto mapea el rango completo para la función duty_u16 de MicroPython,
        # lo que genera una señal de 3.3Vpp con offset de 1.65V CC en el pin GP17.
        self.wavetable = [
            int((math.sin(2 * math.pi * i / self.table_size) + 1) * 32767)
            for i in range(self.table_size)
        ]
        
        # Acumulador de fase persistente en formato de Punto Fijo (escalado por 2^16 = 65536)
        self.current_phase_fixed = 0

    @property
    def current_phase(self):
        """
        Propiedad de compatibilidad con versiones anteriores que devuelve la fase en float.
        """
        return self.current_phase_fixed / 65536.0

    @current_phase.setter
    def current_phase(self, value):
        """
        Propiedad de compatibilidad para establecer la fase a partir de un float.
        """
        self.current_phase_fixed = int(value * 65536)

    def transmit_burst(self, bits, baud_rate, fs, f_mark, f_space, pwm_device):
        """
        Sintetiza y transmite en tiempo real una ráfaga de bits con fase continua
        utilizando un lazo optimizado de cero asignaciones de memoria (Zero-Allocation)
        y un watchdog de seguridad térmica por software.

        Args:
            bits (list[int]): Lista de bits (0 y 1) a modular.
            baud_rate (int): Velocidad en baudios (50, 150, 300, 600, 1200).
            fs (int): Frecuencia de muestreo virtual (Hz).
            f_mark (int): Frecuencia del tono para bit '1' (Hz).
            f_space (int): Frecuencia del tono para bit '0' (Hz).
            pwm_device: Objeto PWM configurado en hal.py.
        """
        # Constantes de escala para Punto Fijo (16 bits de fracción)
        SCALE_SHIFT = 16
        SCALE = 65536
        
        # Cálculo de límites y máscaras binarias rápidas
        max_phase = self.table_size * SCALE
        phase_mask = max_phase - 1  # Máscara para la envoltura circular rápida (AND)
        
        # Muestras enteras por bit
        samples_per_bit = fs // baud_rate
        
        # Incremento de fase en formato Punto Fijo (evita punto flotante en el bucle)
        inc_mark = int((f_mark * self.table_size * SCALE) // fs)
        inc_space = int((f_space * self.table_size * SCALE) // fs)
        
        # Límite absoluto de tiempo de transmisión (watchdog) en microsegundos
        max_tx_us = config.MAX_TX_TIME_S * 1_000_000
        
        # Cachear funciones y referencias locales
        # En MicroPython, las búsquedas locales son significativamente más rápidas
        # que buscar atributos de objetos o globales en el diccionario.
        duty_u16 = pwm_device.duty_u16
        wavetable = self.wavetable
        ticks_us = time.ticks_us
        ticks_add = time.ticks_add
        ticks_diff = time.ticks_diff
        sleep_us_func = time.sleep_us
        
        # Cargar fase persistente actual en variable local del lazo
        phase_fixed = self.current_phase_fixed
        
        # Desactivación preventiva del Garbage Collector para blindar el tiempo crítico
        # de cualquier interrupción o limpieza automática del intérprete.
        gc.disable()
        gc.collect()  # Forzar una recolección limpia justo antes del envío
        
        # Captura del tiempo inicial absoluto
        start_time = ticks_us()
        target_us = start_time
        time_accumulator = 0
        
        try:
            for bit in bits:
                # Selección estricta del incremento de fase sin asignación de memoria
                phase_inc = inc_mark if bit == 1 else inc_space
                
                for _ in range(samples_per_bit):
                    # 1. Inyección de la muestra analógica precomputada (cero float math)
                    # Se desplaza 16 bits para obtener el índice entero de la tabla circular
                    duty_u16(wavetable[phase_fixed >> SCALE_SHIFT])
                    
                    # 2. Modulación de fase: avance continuo con envoltura binaria plana (cero float mod)
                    phase_fixed = (phase_fixed + phase_inc) & phase_mask
                    
                    # 3. Lazo de Control de Tiempo Absoluto Incremental (Cero Bignums)
                    # Acumula microsegundos fraccionales de forma entera para evitar decimales y derivas
                    time_accumulator += 1_000_000
                    us_step = time_accumulator // fs
                    time_accumulator %= fs
                    
                    target_us = ticks_add(target_us, us_step)
                    sleep_us = ticks_diff(target_us, ticks_us())
                    
                    # 4. Watchdog de Seguridad Térmica (Límite Máximo de TX)
                    # Compara la duración acumulada de forma directa y libre de asignación de heap
                    if ticks_diff(ticks_us(), start_time) > max_tx_us:
                        raise RuntimeError("TIMEOUT_PROTECTION_PA")
                    
                    # Suspensión precisa de la CPU
                    if sleep_us > 0:
                        sleep_us_func(sleep_us)
                    elif sleep_us < -1000:
                        # En caso de demora extrema, se recalibra el cronómetro absoluto de forma segura
                        target_us = ticks_us()
                        time_accumulator = 0
        finally:
            # Guardar el acumulador de fase final de forma persistente para la siguiente ráfaga
            self.current_phase_fixed = phase_fixed
            # Reactivar el recolector de basura de forma limpia e inocua
            gc.enable()
            gc.collect()

    def reset_phase(self):
        """Reinicia el acumulador de fase a cero."""
        self.current_phase_fixed = 0
