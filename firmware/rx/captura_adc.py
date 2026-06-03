import machine
import array
import gc
import config
import _thread
import time

# Inicialización del Hardware ADC
adc = machine.ADC(config.ADC_PIN)

# --- VARIABLES DE DOBLE BÚFER ---
BUFFER_SIZE = config.SAMPLE_RATE  # 1.0 segundo de audio dinámico según config

# Pre-asignar dos buffers de tipo array de enteros con signo de 16 bits ('h')
# Esto garantiza cero allocations durante el muestreo en caliente
buffer_0 = array.array('h', [0] * BUFFER_SIZE)
buffer_1 = array.array('h', [0] * BUFFER_SIZE)
buffers = [buffer_0, buffer_1]

active_buffer_idx = 0
current_sample_idx = 0
buffer_ready = False
ready_buffer_idx = 1
streaming_active = False

def captura_core1():
    """
    Bucle de digitalización en caliente en Core 1.
    Muestrea a config.SAMPLE_RATE Hz en el búfer activo.
    Al completarse las muestras de un bloque de un segundo, conmuta de búfer y activa buffer_ready.
    """
    global active_buffer_idx, current_sample_idx, buffer_ready, ready_buffer_idx, streaming_active
    
    gc.disable()
    
    period = int(1000000 / config.SAMPLE_RATE)  # 52 us a 19200 Hz
    next_time = time.ticks_us()
    
    try:
        while streaming_active:
            # Busy-wait
            while time.ticks_diff(time.ticks_us(), next_time) < 0:
                if not streaming_active:
                    break
            
            if not streaming_active:
                break
                
            next_time += period
            
            # Leer el ADC (0-65535) y centrarlo a 16 bits signed PCM (-32768 a 32767)
            # Esto es lo que corresponde al 16-bit PCM original centrado
            val_signed = adc.read_u16() - 32768
            
            # Escribir en el búfer activo sin allocations
            buffers[active_buffer_idx][current_sample_idx] = val_signed
            current_sample_idx += 1
            
            # Si se llenó el búfer de 1 segundo
            if current_sample_idx >= BUFFER_SIZE:
                current_sample_idx = 0
                ready_buffer_idx = active_buffer_idx
                active_buffer_idx = 1 - active_buffer_idx
                buffer_ready = True
                
    except Exception as e:
        print(f"[Core 1] Error en digitalizacion: {e}")
    finally:
        streaming_active = False
        gc.enable()

def iniciar_grabacion_streaming():
    """Inicia el hilo de digitalización de doble búfer en Core 1."""
    global active_buffer_idx, current_sample_idx, buffer_ready, streaming_active
    
    active_buffer_idx = 0
    current_sample_idx = 0
    buffer_ready = False
    streaming_active = True
    
    print("[ADC] 📡 Iniciando digitalizacion de doble bufer en Core 1...")
    _thread.start_new_thread(captura_core1, ())
    return True

def obtener_buffer_listo():
    """Retorna el búfer que se acaba de llenar y limpia la bandera."""
    global buffer_ready
    buffer_ready = False
    return buffers[ready_buffer_idx]

def detener_grabacion():
    """Detiene el bucle de digitalización."""
    global streaming_active
    streaming_active = False
    time.sleep_ms(20)  # Permitir finalización ordenada
    return True

def liberar_memoria():
    """En streaming de doble búfer no hay buffers dinámicos gigantes que liberar,
    pero hacemos una recolección de basura para limpiar el Heap."""
    gc.collect()
    print(f"[MEM] GC ejecutado. Heap libre: {gc.mem_free() / 1024:.2f} KB")

def obtener_estado():
    """Retorna el estado para el polling tradicional (compatibilidad)."""
    return {
        "grabando": streaming_active,
        "muestras": 0,
        "segundos": 0.0,
        "max_segundos": 9999.0
    }
