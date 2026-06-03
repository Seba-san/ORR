import gc
import time
import socket
import red_wifi
import captura_adc
import config

def correr_test_real(puerto=8080):
    """
    Ejecuta un servidor TCP real en la Pico W, configurando el Punto de Acceso.
    Mide la latencia de transmisión Wi-Fi física de cada bloque de audio de 1.0s,
    detecta si ocurren Overruns en los buffers del ADC y monitorea el Heap de RAM.
    """
    print("=========================================================================")
    print("        INICIANDO SUITE DE ESTRÉS REAL E2E - WI-FI + ADC EN PICO W")
    print("=========================================================================")
    
    # 1. Configurar y levantar el Punto de Acceso Wi-Fi real
    print(f"[WIFI] Configurando Punto de Acceso '{config.WIFI_SSID}'...")
    ap, ip = red_wifi.configurar_ap(config.WIFI_SSID, config.WIFI_PASS, config.WIFI_IP)
    print(f"[WIFI] AP levantado con éxito. IP del receptor: {ip}")
    
    # 2. Inicializar socket TCP del servidor de pruebas
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        s.bind(('', puerto))
        s.listen(1)
    except Exception as bind_err:
        print(f"[ERROR] No se pudo enlazar el socket al puerto {puerto}: {bind_err}")
        s.close()
        return
        
    print(f"[TCP] Servidor de pruebas escuchando en el puerto: {puerto}")
    print(f"[INFO] 📱 Conecta tu celular/PC a la red Wi-Fi '{config.WIFI_SSID}'")
    print(f"[INFO] 🌍 Abre en el navegador del celular o PC: http://{ip}:{puerto}/")
    print("-------------------------------------------------------------------------")
    print("Esperando conexión de un cliente de red real...")
    
    # Espera bloqueante de conexión de cliente
    conn = None
    try:
        conn, addr = s.accept()
        print(f"[TCP] ¡Cliente conectado exitosamente desde {addr[0]}:{addr[1]}!")
        
        # Intentar leer los bytes de petición HTTP para no romper clientes web
        try:
            conn.settimeout(2.0)
            request_bytes = conn.recv(1024)
            request = request_bytes.decode('utf-8') if request_bytes else ""
            print(f"[HTTP] Petición inicial recibida:\n{request[:120]}...\n")
        except Exception:
            request = ""
            print("[HTTP] No se detectó cabecera HTTP estándar. Transmitiendo stream en bruto...")
        finally:
            conn.settimeout(None)  # Quitar timeout para la transmisión de largo plazo
            
        # Si es un navegador, enviarle cabeceras HTTP estándar para habilitar el streaming de bytes
        if "GET" in request:
            headers = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/octet-stream\r\n"
                "Connection: keep-alive\r\n"
                "Cache-Control: no-cache\r\n\r\n"
            )
            conn.sendall(headers.encode('utf-8'))
            print("[HTTP] Cabeceras de flujo enviadas al navegador.")
            
    except KeyboardInterrupt:
        print("\n[INFO] Test cancelado por el operador antes de recibir conexión.")
        s.close()
        return
    except Exception as accept_err:
        print(f"[ERROR] Error al aceptar cliente: {accept_err}")
        s.close()
        return

    # 3. Levantar digitalización real de hardware ADC en el Core 1
    exito = captura_adc.iniciar_grabacion_streaming()
    if not exito:
        print("[ERROR] Falló el inicio de captura de audio del ADC.")
        try:
            conn.close()
        except:
            pass
        s.close()
        return
        
    print("[ADC] Digitalización activa en Core 1 a 19200 Hz con Doble Búfer.")
    print("\n--- INICIANDO PROTOCOLO DE ESTRÉS REAL E2E ---")
    print("Tiempo (MM:SS) | RAM Libre (KB) | Latencia Wi-Fi (ms) | Overruns | Estado")
    print("-------------------------------------------------------------------------")
    
    # Variables de telemetría de rendimiento
    gc.collect()
    ram_inicial = gc.mem_free()
    ram_minima = ram_inicial
    max_latencia = 0.0
    latencias_acumuladas = 0.0
    overruns = 0
    total_bloques = 0
    inicio_test = time.time()
    
    try:
        while True:
            # Esperar a que el Core 1 complete y entregue un buffer de 1.0 segundo (19200 muestras)
            timeout_start = time.ticks_ms()
            while not captura_adc.buffer_ready:
                if not captura_adc.streaming_active:
                    raise RuntimeError("La captura de Core 1 se ha apagado.")
                if time.ticks_diff(time.ticks_ms(), timeout_start) > 2000:
                    raise RuntimeError("Timeout esperando al Core 1 (Adquisición bloqueada).")
                time.sleep_ms(10)
                
            # Extraer el buffer listo
            buf = captura_adc.obtener_buffer_listo()
            total_bloques += 1
            
            # --- MEDIR LATENCIA DE TRANSMISIÓN WI-FI (BLOQUEO DE RED) ---
            t_envio_inicio = time.ticks_us()
            conn.sendall(buf)
            t_envio_fin = time.ticks_us()
            
            latencia_ms = time.ticks_diff(t_envio_fin, t_envio_inicio) / 1000.0
            latencias_acumuladas += latencia_ms
            if latencia_ms > max_latencia:
                max_latencia = latencia_ms
                
            # --- CONTROL Y LIMPIEZA DE MEMORIA DINÁMICA ---
            gc.collect()
            ram_libre = gc.mem_free()
            if ram_libre < ram_minima:
                ram_minima = ram_libre
                
            # --- DETECCIÓN DE OVERRUN DE CORE 1 ---
            # Si justo después del envío TCP y limpieza de RAM el 'buffer_ready' ya vuelve a estar
            # en True, significa que Core 1 completó el siguiente búfer de un segundo mientras Core 0
            # estaba ocupado transmitiendo el anterior. ¡Esto es pérdida o distorsión de muestras!
            overrun_detectado = False
            if captura_adc.buffer_ready:
                overruns += 1
                overrun_detectado = True
                
            # --- REGISTRO DE TELEMETRÍA ---
            transcurrido = time.time() - inicio_test
            minutos = int(transcurrido) // 60
            segundos = int(transcurrido) % 60
            
            # Formatear visualmente el estado del ciclo actual
            estado_str = "OK"
            if overrun_detectado:
                estado_str = "OVERRUN ⚠️"
            if latencia_ms > 1000.0:
                estado_str += " (LENTO 🐢)"
                
            print(f"  {minutos:02d}:{segundos:02d}        | {ram_libre/1024:7.2f} KB  | {latencia_ms:8.1f} ms        | {overruns:8d} | {estado_str}")
            
    except Exception as stream_err:
        print(f"\n[INFO] Conexión finalizada o interrumpida por red/cliente: {stream_err}")
    finally:
        # 4. Apagar hardware ADC y cerrar sockets de forma ultra segura
        captura_adc.detener_grabacion()
        captura_adc.liberar_memoria()
        try:
            conn.close()
        except:
            pass
        try:
            s.close()
        except:
            pass
        print("-------------------------------------------------------------------------")
        
    # 5. Imprimir Reporte Final Comparativo
    transcurrido_total = time.time() - inicio_test
    print("\n================ RESUMEN DE ESTRÉS REAL E2E ================")
    print(f" Duración de transmisión activa : {transcurrido_total:.1f} segundos")
    print(f" Total de bloques transmitidos  : {total_bloques}")
    print(f" RAM inicial libre en Pico W    : {ram_inicial / 1024:.2f} KB")
    print(f" RAM mínima libre registrada    : {ram_minima / 1024:.2f} KB")
    print(f" Fluctuación neta de RAM        : {(ram_inicial - ram_minima) / 1024:.2f} KB")
    print(f" Latencia Wi-Fi máxima de envío : {max_latencia:.2f} ms")
    if total_bloques > 0:
        print(f" Latencia Wi-Fi promedio de envío: {latencias_acumuladas / total_bloques:.2f} ms")
    print(f" Bloques perdidos por Overrun   : {overruns}")
    
    # Diagnóstico Final de Rendimiento de Campo
    print("------------------------------------------------------------")
    if overruns == 0 and max_latencia < 800.0:
        print(" DIAGNÓSTICO E2E: ¡EXCELENTE! Conexión Wi-Fi rápida y estable.")
        print(" El firmware mantiene holgura y es 100% confiable a largo plazo.")
    else:
        print(" DIAGNÓSTICO E2E: ¡ADVERTENCIA!")
        if overruns > 0:
            print(f" -> Se perdieron {overruns} bloques debido a Overruns. El Wi-Fi bloquea la CPU por > 1.0s.")
        if max_latencia >= 1000.0:
            print(f" -> Latencia máxima alarmante ({max_latencia:.1f} ms). Revisa distancias u obstáculos.")
    print("============================================================\n")
