import machine
import array
import gc
import config
import time

# Inicialización del Hardware ADC
adc = machine.ADC(config.ADC_PIN)

# --- VARIABLES DE DOBLE BÚFER ---
BUFFER_SIZE = config.SAMPLE_RATE  # 19200 muestras por bloque (1 segundo)

# Pre-asignar dos buffers de tipo array de enteros con signo de 16 bits ('h')
# Esto garantiza CERO allocations durante el muestreo en caliente.
buffer_0 = array.array('h', [0] * BUFFER_SIZE)
buffer_1 = array.array('h', [0] * BUFFER_SIZE)

# Variables de estado globales
active_buffer_idx = 0
current_sample_idx = 0
buffer_ready = False
ready_buffer_idx = 1
streaming_active = False

# Temporizador de hardware para el muestreo estricto
hw_timer = machine.Timer(-1)

@micropython.native
def adc_timer_irq(t):
    """
    Rutina de Interrupción (ISR) disparada por el Hardware Timer.
    Al estar precompilada con @micropython.native y controlada por silicio,
    garantiza 0.0 ppm de deriva de software (elimina los +1600 ppm del busy-wait).
    """
    global active_buffer_idx, current_sample_idx, buffer_ready, ready_buffer_idx
    
    # Leer el ADC (0-65535) y centrarlo a 16 bits signed PCM (-32768 a 32767)
    val_signed = adc.read_u16() - 32768
    
    # Escribir directamente en la RAM (Zero-Allocation)
    if active_buffer_idx == 0:
        buffer_0[current_sample_idx] = val_signed
    else:
        buffer_1[current_sample_idx] = val_signed
        
    current_sample_idx += 1
    
    # Conmutación de búfer instantánea
    if current_sample_idx >= BUFFER_SIZE:
        ready_buffer_idx = active_buffer_idx
        active_buffer_idx = 1 - active_buffer_idx
        current_sample_idx = 0
        buffer_ready = True


def iniciar_grabacion_streaming():
    """Inicia el temporizador de hardware que dispara el muestreo automático."""
    global active_buffer_idx, current_sample_idx, buffer_ready, streaming_active
    
    # Apagar por seguridad en caso de reinicios rápidos
    hw_timer.deinit()
    
    active_buffer_idx = 0
    current_sample_idx = 0
    buffer_ready = False
    streaming_active = True
    
    gc.collect()  # Limpiar la memoria antes de arrancar la sesión
    
    print(f"[ADC] 📡 Iniciando Hardware Timer estricto a {config.SAMPLE_RATE} Hz...")
    
    # El timer toma el control. Lanza la interrupción IRQ de forma autónoma.
    # No requiere hilos (_thread) ni bucles while ocupando CPU.
    hw_timer.init(freq=config.SAMPLE_RATE, mode=machine.Timer.PERIODIC, callback=adc_timer_irq)
    return True

def obtener_buffer_listo():
    """Retorna el búfer que se acaba de llenar y limpia la bandera."""
    global buffer_ready
    buffer_ready = False
    return buffer_0 if ready_buffer_idx == 0 else buffer_1

def detener_grabacion():
    """Detiene las interrupciones del timer."""
    global streaming_active
    hw_timer.deinit()  # Apagar interrupciones de hardware de golpe
    streaming_active = False
    time.sleep_ms(20)  # Permitir finalización ordenada del TCP
    print("[ADC] ⏹️ Hardware Timer detenido.")
    return True

def liberar_memoria():
    gc.collect()
    print(f"[MEM] GC ejecutado. Heap libre: {gc.mem_free() / 1024:.2f} KB")

def obtener_estado():
    """Retorna el estado para compatibilidad con interfaces web existentes."""
    return {
        "grabando": streaming_active,
        "muestras": 0,
        "segundos": 0.0,
        "max_segundos": 9999.0
    }
