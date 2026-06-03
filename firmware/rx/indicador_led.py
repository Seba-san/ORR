import machine

# Inicializar el pin del LED integrado
try:
    # En la Pico W / Pico 2W, el LED está conectado al chip CYW43
    led = machine.Pin("LED", machine.Pin.OUT)
except Exception:
    # Fallback para placas Pico clásicas sin chip inalámbrico (Pin GP25)
    try:
        led = machine.Pin(25, machine.Pin.OUT)
    except Exception:
        led = None

# Variable global para el Timer del LED y el estado actual
_timer_led = None
_estado_actual = None

def _toggle_led(t):
    """Rutina para cambiar el estado del LED (ON/OFF)."""
    if led:
        led.value(not led.value())

def _limpiar_timer():
    """Detiene y elimina de forma segura el temporizador activo del LED."""
    global _timer_led
    if _timer_led is not None:
        try:
            _timer_led.deinit()
        except Exception:
            pass
        _timer_led = None

def establecer_estado(estado):
    """
    Establece el estado de indicación del LED integrado.
    
    Estados válidos:
    - 'esperando': Alimentación conectada, parpadeo medio (500ms ON / 500ms OFF).
    - 'conectado': Celular ingresó a la web, parpadeo rápido (100ms ON / 100ms OFF).
    - 'grabando': Transmisión ADC activa, luz fija encendida.
    """
    global _timer_led, _estado_actual
    
    if led is None:
        return
        
    if estado == _estado_actual:
        return
        
    _estado_actual = estado
    _limpiar_timer()
    
    if estado == 'esperando':
        print("[LED] Estado: Esperando cliente (parpadeo medio)")
        led.off()
        _timer_led = machine.Timer(-1)
        _timer_led.init(period=500, mode=machine.Timer.PERIODIC, callback=_toggle_led)
        
    elif estado == 'conectado':
        print("[LED] Estado: Celular conectado (parpadeo rápido)")
        led.off()
        _timer_led = machine.Timer(-1)
        _timer_led.init(period=100, mode=machine.Timer.PERIODIC, callback=_toggle_led)
        
    elif estado == 'grabando':
        print("[LED] Estado: Grabando audio (Luz fija encendida)")
        led.on()
        
    else:
        # Estado desconocido, apagar por seguridad
        print(f"[LED] Estado desconocido '{estado}'. Apagando LED.")
        led.off()
