"""
main.py — Orquestador de la Máquina de Estados (FSM) y Gestión de Transmisión
============================================================================
Proyecto : Comunicación Digital sobre Radios Analógicas FM (JAR 2026)
Instituto: Instituto de Automática (INAUT) — UNSJ — CONICET
Hardware : Raspberry Pi Pico 2W (RP2350) + Baofeng UV-82

Este es el script de entrada (main) del transmisor optimizado para campo.
Se han eliminado por completo los reportes detallados por el puerto USB-UART
para maximizar la velocidad de ejecución del lazo y evitar el uso de buffers
de transmisión serie innecesarios, garantizando un funcionamiento silencioso.
============================================================================
"""

import time
import gc
import config
from hal import HAL
from lfsr import LFSR
from modulator import AFSKModulator


# Definición de Estados de la FSM
STATE_IDLE         = 0
STATE_PTT_ON       = 1
STATE_TRANSMIT     = 2
STATE_PTT_OFF      = 3
STATE_COOLDOWN     = 4
STATE_COMPLETED    = 5
STATE_PRE_WAIT     = 6


def debug_log(tag, message):
    """
    Imprime mensajes de depuración formateados a través del puerto serie
    si la bandera DEBUG en config.py está activa.
    """
    if config.DEBUG:
        # Formateo ordenado y tabulado de tags para Thonny
        print("[{:8s}] {}".format(tag, message))

def led_blink_pattern(hal, pattern_type):
    """
    Patrones de destello de LED para interactuar de forma intuitiva con el operador.
    """
    if pattern_type == "boot":
        # Parpadeo triple rápido al iniciar
        for _ in range(3):
            hal.set_led(True)
            time.sleep_ms(100)
            hal.set_led(False)
            time.sleep_ms(100)
    elif pattern_type == "session_complete":
        # Parpadeo rápido sostenido al terminar la sesión completa de 12700 bits
        for _ in range(5):
            hal.set_led(True)
            time.sleep_ms(50)
            hal.set_led(False)
            time.sleep_ms(50)

def main():
    # Inicializar Abstracciones de Hardware y Algoritmos
    hal = HAL()

    # Indicar arranque exitoso con parpadeo físico INMEDIATAMENTE
    # Esto asegura retroalimentación visual al resetear con batería, antes de cualquier print serie.
    led_blink_pattern(hal, "boot")

    lfsr = LFSR()
    modulator = AFSKModulator(table_size=config.TABLE_SIZE)

    # Mostrar arranque exitoso e informar al operador
    debug_log("SISTEMA", "=== INICIANDO TRANSMISOR AFSK (RP2350) ===")
    debug_log("SISTEMA", "Pines de hardware: PWM_TX=GP{}, PTT=GP{}, TRIGGER=GP{}".format(
        config.PIN_PWM_TX, config.PIN_PTT, config.PIN_TRIGGER
    ))
    debug_log("SISTEMA", "Parámetros AFSK: Mark={} Hz, Space={} Hz | Muestreo (Fs)={} Hz".format(
        config.F_MARK, config.F_SPACE, config.FS
    ))
    debug_log("SISTEMA", "Trama de velocidades cíclicas (Baudios): {}".format(config.BAUD_RATES))

    # Generar secuencia binaria pseudoaleatoria patrón PRBS-7
    prbs_seq = lfsr.generate_sequence()
    debug_log("PRBS-7", "Secuencia PRBS-7 generada (127 bits).")
    debug_log("PRBS-7", " - Balance: {} unos (1s), {} ceros (0s)".format(
        sum(prbs_seq), len(prbs_seq) - sum(prbs_seq)
    ))

    # Variables de control de velocidad y de estados de la FSM
    current_baud_idx = 0
    fsm_state = STATE_IDLE
    
    session_baud = config.BAUD_RATES[current_baud_idx]
    bursts_total = 0
    burst_current = 0
    burst_bits_list = []
    
    # Registros para cálculos térmicos y control
    t_tx_start = 0
    t_tx_real = 0
    t_cooldown_start = 0
    t_cooldown_duration = 0
    
    # Variable para controlar la cuenta regresiva periódica en Thonny
    last_cooldown_sec_printed = -1

    # Variables para el control de la cuenta regresiva de pre-espera (caminata)
    pre_wait_start = 0
    last_minute_processed = -1
    last_second_printed = -1

    debug_log("FSM", "Estado: IDLE. Esperando flanco GP2 (gatillo)...")

    # Variable para monitorear el tiempo de pulsación del botón GP2
    button_press_start = None

    try:
        while True:
            # --- SISTEMA DE REINICIO POR SOFTWARE MEDIANTE GATILLO (Pulsación de 3 segundos) ---
            # Solo se verifica en estados no críticos de modulación (fuera de STATE_TRANSMIT)
            if fsm_state != STATE_TRANSMIT:
                if hal.trigger.value() == 0:  # Botón presionado (activo en BAJO)
                    if button_press_start is None:
                        button_press_start = time.ticks_ms()
                    else:
                        elapsed = time.ticks_diff(time.ticks_ms(), button_press_start)
                        if elapsed > 3000:  # 3 segundos
                            debug_log("SISTEMA", "¡REINICIO DE SOFTWARE INICIADO POR EL OPERADOR (Pulsación larga GP2)!")
                            # Patrón de advertencia visual rápido en el LED
                            for _ in range(15):
                                hal.set_led(True)
                                time.sleep_ms(40)
                                hal.set_led(False)
                                time.sleep_ms(40)
                            import machine
                            machine.reset()
                else:
                    button_press_start = None
            # ========================================================================
            #  ESTADO: IDLE (Reposo y Monitoreo del Gatillo GP2)
            # ========================================================================
            if fsm_state == STATE_IDLE:
                if hal.check_trigger_rising_edge():
                    if config.AUTONOMOUS_MODE:
                        debug_log("GATILLO", "¡Gatillo detectado! Modo AUTÓNOMO activo.")
                        debug_log("GATILLO", " - Iniciando cuenta regresiva de pre-espera: {} minutos".format(config.PRE_WAIT_MINUTES))
                        
                        pre_wait_start = time.ticks_ms()
                        last_minute_processed = -1
                        last_second_printed = -1
                        fsm_state = STATE_PRE_WAIT
                    else:
                        # Modo Laboratorio: Iniciar transmisión inmediata de la velocidad actual
                        session_baud = config.BAUD_RATES[current_baud_idx]
                        frag_info = config.FRAGMENTATION[session_baud]
                        
                        burst_bits = frag_info["burst_bits"]
                        bursts_total = frag_info["bursts"]
                        
                        debug_log("GATILLO", "¡Gatillo detectado! Modo LABORATORIO activo (inmediato).")
                        debug_log("GATILLO", " - Velocidad de ensayo: {} baudios".format(session_baud))
                        debug_log("GATILLO", " - Plan de ráfagas: {} bursts de {} bits".format(bursts_total, burst_bits))
                        
                        # Preparar los bits para la ráfaga repitiendo la secuencia PRBS-7
                        repetitions = burst_bits // len(prbs_seq)
                        burst_bits_list = prbs_seq * repetitions
                        
                        burst_current = 0
                        fsm_state = STATE_PTT_ON


            # ========================================================================
            #  ESTADO: PRE_WAIT (Cuenta Regresiva y Emisión de Tonos de Presencia)
            # ========================================================================
            elif fsm_state == STATE_PRE_WAIT:
                # Calcular el tiempo transcurrido en segundos
                elapsed_ms = time.ticks_diff(time.ticks_ms(), pre_wait_start)
                elapsed_s = elapsed_ms // 1000
                total_wait_s = config.PRE_WAIT_MINUTES * 60
                
                if elapsed_s >= total_wait_s:
                    debug_log("PRE-WAIT", "¡Cuenta regresiva de pre-espera finalizada con éxito!")
                    
                    # Preparar los parámetros de transmisión para la primera ráfaga
                    session_baud = config.BAUD_RATES[current_baud_idx]
                    frag_info = config.FRAGMENTATION[session_baud]
                    burst_bits = frag_info["burst_bits"]
                    bursts_total = frag_info["bursts"]
                    
                    debug_log("TX_START", "Iniciando transmisión de ensayo a {} baudios.".format(session_baud))
                    debug_log("TX_START", " - Plan de ráfagas: {} bursts de {} bits".format(bursts_total, burst_bits))
                    
                    # Preparar los bits repitiendo la secuencia PRBS-7
                    repetitions = burst_bits // len(prbs_seq)
                    burst_bits_list = prbs_seq * repetitions
                    
                    burst_current = 0
                    fsm_state = STATE_PTT_ON
                else:
                    # Mostrar cuenta regresiva de forma ordenada segundo a segundo
                    remaining_s = total_wait_s - elapsed_s
                    if remaining_s != last_second_printed:
                        rem_min = remaining_s // 60
                        rem_sec = remaining_s % 60
                        debug_log("PRE-WAIT", "Tiempo para la transmisión: {:02d}:{:02d}".format(rem_min, rem_sec))
                        last_second_printed = remaining_s
                    
                    # Hacer parpadear el LED lentamente para indicar estado ocupado en pre-espera
                    # Ciclo de 1000 ms: encendido 100 ms, apagado 900 ms
                    cycle_pos = elapsed_ms % 1000
                    if cycle_pos < 100:
                        hal.set_led(True)
                    else:
                        hal.set_led(False)
                    
                    # Determinar minuto y segundo actual
                    m = elapsed_s // 60
                    sec_in_min = elapsed_s % 60
                    
                    # En el segundo 55 del minuto actual (salvo el último minuto), emitir aviso de 3s
                    if m < config.PRE_WAIT_MINUTES - 1 and sec_in_min == 55:
                        if last_minute_processed != m:
                            last_minute_processed = m
                            remaining_minutes = config.PRE_WAIT_MINUTES - 1 - m
                            
                            debug_log("PRE-WAIT", "Emitiendo aviso del minuto {} (Faltan {} minutos)...".format(m + 1, remaining_minutes))
                            
                            # Decidir si mandar el patrón pre-anuncio o el tono puro de 2400 Hz
                            if remaining_minutes == 2 or remaining_minutes == 1:
                                debug_log("PRE-WAIT", " -> Mandando patrón pre-anuncio 01010101 (3s)...")
                                bits_to_send = [0, 1] * 1800  # 3 segundos a 1200 baudios
                            else:
                                debug_log("PRE-WAIT", " -> Mandando tono de presencia 2400 Hz (3s)...")
                                bits_to_send = [0] * 3600  # 3 segundos a 1200 baudios
                            
                            # Realizar transmisión síncrona
                            hal.set_led(True)
                            hal.set_ptt(True)
                            time.sleep_ms(config.PTT_PRE_DELAY_MS)
                            
                            try:
                                modulator.transmit_burst(
                                    bits=bits_to_send,
                                    baud_rate=1200,
                                    fs=config.FS,
                                    f_mark=config.F_MARK,
                                    f_space=config.F_SPACE,
                                    pwm_device=hal.pwm
                                )
                            except Exception as e:
                                debug_log("PRE-WAIT ERROR", "Falla en transmisión de tono: {}".format(e))
                            
                            hal.silence_pwm()
                            time.sleep_ms(config.PTT_POST_DELAY_MS)
                            hal.set_ptt(False)
                            hal.set_led(False)
                            
                            debug_log("PRE-WAIT", "Aviso del minuto {} emitido de forma segura.".format(m + 1))

            # ========================================================================
            #  ESTADO: PTT_ON (Estabilización de Portadora RF)
            # ========================================================================
            elif fsm_state == STATE_PTT_ON:
                debug_log("PTT", "Activando PTT de radio Baofeng y LED indicador...")
                hal.set_led(True)     # LED encendido fijo durante transmisión
                hal.set_ptt(True)     # Activar PTT mediante optoacoplador PC817
                
                # Esperar retardo de apertura del squelch
                debug_log("PTT", "Esperando estabilización de portadora pre-TX ({} ms)...".format(config.PTT_PRE_DELAY_MS))
                time.sleep_ms(config.PTT_PRE_DELAY_MS)
                fsm_state = STATE_TRANSMIT

            # ========================================================================
            #  ESTADO: TRANSMIT (Síntesis Digital CPFSK en Lazo Crítico)
            # ========================================================================
            elif fsm_state == STATE_TRANSMIT:
                debug_log("TX", "Modulando ráfaga {}/{} ({} bits)...".format(
                    burst_current + 1, bursts_total, len(burst_bits_list)
                ))
                t_tx_start = time.ticks_ms()
                
                tx_aborted = False
                try:
                    # Iniciar lazo crítico de modulación sin jitter
                    modulator.transmit_burst(
                        bits=burst_bits_list,
                        baud_rate=session_baud,
                        fs=config.FS,
                        f_mark=config.F_MARK,
                        f_space=config.F_SPACE,
                        pwm_device=hal.pwm
                    )
                except RuntimeError as e:
                    if str(e) == "TIMEOUT_PROTECTION_PA":
                        debug_log("CRÍTICO", "¡ALERTA TÉRMICA! Transmisión abortada por watchdog por superar los {}s.".format(config.MAX_TX_TIME_S))
                        tx_aborted = True
                    else:
                        raise e
                
                hal.silence_pwm()
                t_tx_real = time.ticks_diff(time.ticks_ms(), t_tx_start)
                if tx_aborted:
                    debug_log("TX", "Transmisión ABORTADA por seguridad a los {} ms.".format(t_tx_real))
                else:
                    debug_log("TX", "Ráfaga modulada exitosamente en {} ms (teórico: {} ms)".format(
                        t_tx_real, int((len(burst_bits_list) * 1000) / session_baud)
                    ))
                fsm_state = STATE_PTT_OFF

            # ========================================================================
            #  ESTADO: PTT_OFF (Apagado Seguro del Transmisor)
            # ========================================================================
            elif fsm_state == STATE_PTT_OFF:
                debug_log("PTT", "Esperando retardo de cola post-TX ({} ms) para propagar audio...".format(config.PTT_POST_DELAY_MS))
                # Retardo de cola para que se propaguen las últimas muestras de audio
                time.sleep_ms(config.PTT_POST_DELAY_MS)
                
                hal.set_ptt(False)
                hal.set_led(False)
                debug_log("PTT", "PTT y LED apagados de forma segura.")
                
                # Cálculo de enfriamiento proporcional
                t_ptt_activo_ms = t_tx_real + config.PTT_PRE_DELAY_MS + config.PTT_POST_DELAY_MS
                t_cooldown_prop = int(config.COOLDOWN_RATIO * t_ptt_activo_ms)
                
                # Pausa mínima de enfriamiento del ensayo según la velocidad
                frag_info = config.FRAGMENTATION[session_baud]
                t_cooldown_min_ensayo = frag_info["min_cooldown_s"] * 1000
                
                # Selección del peor caso para máxima seguridad térmica del PA
                t_cooldown_duration = max(
                    t_cooldown_prop, 
                    t_cooldown_min_ensayo, 
                    config.COOLDOWN_MIN_MS
                )
                
                debug_log("TÉRMICO", "Análisis de tiempo de enfriamiento:")
                debug_log("TÉRMICO", " - Ciclo de trabajo proporcional (50%): {} ms".format(t_cooldown_prop))
                debug_log("TÉRMICO", " - Mínimo para metodología de ensayo: {} ms".format(t_cooldown_min_ensayo))
                debug_log("TÉRMICO", " - Mínimo absoluto de protección:      {} ms".format(config.COOLDOWN_MIN_MS))
                debug_log("TÉRMICO", " -> Enfriamiento total requerido:      {:.2f} s".format(t_cooldown_duration / 1000.0))
                
                t_cooldown_start = time.ticks_ms()
                last_cooldown_sec_printed = -1
                fsm_state = STATE_COOLDOWN

            # ========================================================================
            #  ESTADO: COOLDOWN (Mitigación Térmica Obligatoria)
            # ========================================================================
            elif fsm_state == STATE_COOLDOWN:
                elapsed = time.ticks_diff(time.ticks_ms(), t_cooldown_start)
                remaining = t_cooldown_duration - elapsed
                
                if remaining > 0:
                    # Reportar el tiempo de cooldown segundo a segundo en Thonny
                    remaining_s = int(remaining / 1000) + 1
                    if remaining_s != last_cooldown_sec_printed:
                        debug_log("TÉRMICO", "Enfriando PA de radio... Quedan {} segundos...".format(remaining_s))
                        last_cooldown_sec_printed = remaining_s

                    # Hacer parpadear el LED lentamente para notificar el estado ocupado
                    hal.set_led(True)
                    time.sleep_ms(250)
                    hal.set_led(False)
                    time.sleep_ms(250)
                else:
                    debug_log("TÉRMICO", "¡Ciclo de enfriamiento completado!")
                    burst_current += 1
                    if burst_current < bursts_total:
                        debug_log("FSM", "Iniciando ráfaga programada número {}...".format(burst_current + 1))
                        fsm_state = STATE_PTT_ON
                    else:
                        debug_log("FSM", "Ensayo a {} baudios completado para la sesión de 12700 bits.".format(session_baud))
                        # Sesión de ensayo a esta velocidad completada
                        led_blink_pattern(hal, "session_complete")
                        
                        # ¿Es el último baudrate de la lista de velocidades ensayadas?
                        if current_baud_idx == len(config.BAUD_RATES) - 1:
                            debug_log("FSM", "¡SECUENCIA DE TODOS LOS BAUDRATES COMPLETADA CON ÉXITO!")
                            debug_log("FSM", "Bloqueando inicio de nuevos ensayos. Mantenga presionado GP2 por >3s para reiniciar.")
                            fsm_state = STATE_COMPLETED
                        else:
                            if config.AUTONOMOUS_MODE:
                                # Avanzar automáticamente al siguiente baudrate de la lista de velocidades
                                current_baud_idx += 1
                                session_baud = config.BAUD_RATES[current_baud_idx]
                                frag_info = config.FRAGMENTATION[session_baud]
                                
                                burst_bits = frag_info["burst_bits"]
                                bursts_total = frag_info["bursts"]
                                
                                debug_log("FSM", "Avanzando automáticamente al siguiente ensayo: {} baudios".format(session_baud))
                                debug_log("FSM", " - Plan de ráfagas: {} bursts de {} bits".format(bursts_total, burst_bits))
                                
                                # Preparar los bits para la ráfaga de la nueva velocidad
                                repetitions = burst_bits // len(prbs_seq)
                                burst_bits_list = prbs_seq * repetitions
                                
                                burst_current = 0
                                # Transicionar directamente a PTT_ON para iniciar la modulación de forma autónoma
                                fsm_state = STATE_PTT_ON
                            else:
                                # Modo laboratorio: rotar cíclicamente y esperar gatillazo en IDLE para el siguiente ensayo
                                current_baud_idx = (current_baud_idx + 1) % len(config.BAUD_RATES)
                                next_baud = config.BAUD_RATES[current_baud_idx]
                                debug_log("FSM", "Rotación de velocidad: Próximo ensayo se transmitirá a {} baudios.".format(next_baud))
                                
                                debug_log("FSM", "Estado: IDLE. Listo y esperando gatillazo en GP2...")
                                fsm_state = STATE_IDLE



            # ========================================================================
            #  ESTADO: COMPLETED (Secuencia Finalizada - LED de Aviso y Espera de Reset)
            # ========================================================================
            elif fsm_state == STATE_COMPLETED:
                # Patrón: parpadeo de 2 pulsos cortos en un segundo (----I--I----)
                # Periodo de 1000 ms:
                # - 0 a 100 ms: encendido (primer pulso)
                # - 100 a 250 ms: apagado
                # - 250 a 350 ms: encendido (segundo pulso)
                # - 350 a 1000 ms: apagado
                now = time.ticks_ms()
                cycle_pos = now % 1000
                if cycle_pos < 100:
                    hal.set_led(True)
                elif cycle_pos < 250:
                    hal.set_led(False)
                elif cycle_pos < 350:
                    hal.set_led(True)
                else:
                    hal.set_led(False)

            # Retardo mínimo para evitar saturación del planificador
            time.sleep_ms(10)

    except KeyboardInterrupt:
        debug_log("SISTEMA", "Interrupción de teclado detectada. Deteniendo programa de manera ordenada...")
    finally:
        debug_log("SISTEMA", "Liberando periféricos de hardware en la Pico 2W...")
        hal.deinit()
        debug_log("SISTEMA", "--- SISTEMA APAGADO CON SEGURIDAD ---")

if __name__ == "__main__":
    main()
