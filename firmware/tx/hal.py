"""
hal.py — Capa de Abstracción de Hardware (HAL) para la Pico 2W
============================================================================
Proyecto : Comunicación Digital sobre Radios Analógicas FM (JAR 2026)
Instituto: Instituto de Automática (INAUT) — UNSJ — CONICET
Hardware : Raspberry Pi Pico 2W (RP2350) + Baofeng UV-82

Este módulo aísla los accesos a los registros y periféricos del hardware,
proveyendo métodos claros de control para el LED, el PTT, la modulación PWM
y el gatillo físico con detección de flancos y antirrebote por software.
============================================================================
"""

import time
from machine import Pin, PWM
import config

class HAL:
    """
    Abstracción de Hardware (Hardware Abstraction Layer).
    Configura y administra los recursos de hardware de la RP2350.
    """

    def __init__(self):
        # 1. Configuración de LED con mecanismo de contingencia para el direccionamiento
        try:
            self.led = Pin(config.PIN_LED, Pin.OUT)
        except Exception:
            # Fallback en caso de que "LED" no esté mapeado en la versión de MicroPython
            self.led = Pin(25, Pin.OUT)
        self.led.value(0)

        # 2. Configuración de PTT (GP16) — Salida de control para optoacoplador PC817
        self.ptt = Pin(config.PIN_PTT, Pin.OUT)
        self.ptt.value(0)

        # 3. Configuración de Botón de Gatillo (GP2) — Con pull-up interna
        # Activo en BAJO (conecta a GND al presionarse, lee 0).
        # Inactivo en ALTO (lee 1 debido al pull-up).
        self.trigger = Pin(config.PIN_TRIGGER, Pin.IN, Pin.PULL_UP)

        # 4. Configuración de Audio PWM (GP17)
        self.pwm_pin = Pin(config.PIN_PWM_TX)
        self.pwm = PWM(self.pwm_pin)
        self.pwm.freq(config.F_PWM)
        self.pwm.duty_u16(0)  # Silencio inicial

        # 5. Variables de estado para antirrebote e inmunidad a ruidos (Button Debounce)
        self.last_button_state = self.trigger.value()
        self.last_trigger_time = 0

    def check_trigger_rising_edge(self):
        """
        Monitorea el pin de gatillo y detecta el flanco ascendente (liberación del botón).
        Implementa un periodo de bloqueo temporal (lockout) por software para filtrar
        rebotes mecánicos de los contactos e inducción por acoplamiento de RF.

        Returns:
            bool: True si se detectó una liberación de botón válida fuera del bloqueo,
                  False en cualquier otro caso.
        """
        current_state = self.trigger.value()
        triggered = False

        # Flanco ascendente: de 0 (pulsado) a 1 (liberado)
        if self.last_button_state == 0 and current_state == 1:
            now = time.ticks_ms()
            # Medimos la diferencia respecto al último disparo válido aceptado
            if time.ticks_diff(now, self.last_trigger_time) > config.TRIGGER_LOCKOUT_MS:
                self.last_trigger_time = now
                triggered = True

        self.last_button_state = current_state
        return triggered

    def set_ptt(self, state):
        """
        Controla el estado del pin PTT (transmisión por optoacoplador).
        
        Args:
            state (bool): True para iniciar transmisión, False para recibir.
        """
        self.ptt.value(1 if state else 0)

    def set_led(self, state):
        """
        Controla el estado del LED indicador.
        
        Args:
            state (bool): True para encender, False para apagar.
        """
        self.led.value(1 if state else 0)

    def set_pwm_duty(self, duty):
        """
        Establece directamente el ciclo de trabajo del audio PWM.
        
        Args:
            duty (int): Nivel analógico de 16 bits (0 a 65535).
        """
        self.pwm.duty_u16(duty)

    def silence_pwm(self):
        """Apaga la portadora PWM de audio (silencio absoluto)."""
        self.pwm.duty_u16(0)

    def deinit(self):
        """Libera de manera segura todos los recursos de hardware."""
        self.silence_pwm()
        try:
            self.pwm.deinit()
        except Exception:
            pass
        self.ptt.value(0)
        self.led.value(0)
