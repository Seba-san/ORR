import socket
import gc
import json
import time
import captura_adc
import indicador_led

def enviar_html_chunked(conn):
    """
    Lee index.html en bloques pequeños de 1024 bytes y los envía por el socket.
    Evita saturar el búfer de salida TCP de MicroPython y ahorra memoria RAM.
    """
    try:
        with open('index.html', 'rb') as f:
            while True:
                chunk = f.read(1024)
                if not chunk:
                    break
                conn.sendall(chunk)
    except Exception as e:
        print(f"Error sirviendo index.html en bloques: {e}")
        try:
            conn.send('HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/plain\r\n\r\nError sirviendo HTML'.encode('utf-8'))
        except Exception:
            pass

def iniciar_servidor(puerto):
    """
    Inicia el servidor HTTP / Sockets TCP.
    Sirve el dashboard web y el stream de audio en tiempo real.
    """
    from machine import WDT
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', puerto))
    s.listen(1)
    
    # 1. Establecer timeout de 5.0 segundos en el socket de escucha del servidor
    # Esto permite liberar el s.accept() bloqueante periódicamente para alimentar al Watchdog
    s.settimeout(5.0)
    
    # 2. Inicializar el Hardware Watchdog Timer (WDT) de 8.0 segundos
    wdt = WDT(timeout=8000)
    
    print(f"Servidor web escuchando en el puerto {puerto}...")
    print("Abre el navegador en el celular para comenzar a grabar.\n")
    
    try:
        while True:
            # Alimentar al Watchdog al inicio de cada ciclo de escucha
            wdt.feed()
            
            try:
                conn, addr = s.accept()
            except OSError:
                # Timeout de s.accept() sin clientes conectados.
                # Volvemos a alimentar y esperar.
                continue
                
            try:
                # Establecer un timeout razonable para recibir la petición inicial HTTP
                conn.settimeout(2.0)
                try:
                    request_bytes = conn.recv(1024)
                    if not request_bytes:
                        conn.close()
                        continue
                    request = request_bytes.decode('utf-8')
                except Exception as recv_err:
                    conn.close()
                    continue
                
                # --- RUTA DE STREAMING DE AUDIO EN VIVO ---
                if 'GET /stream' in request:
                    print(f"[{addr[0]}] 📡 Petición de inicio de streaming de audio en tiempo real...")
                    
                    # 1. Iniciar digitalización en Core 1
                    exito = captura_adc.iniciar_grabacion_streaming()
                    
                    if exito:
                        # Poner LED fijo: digitalizando activamente
                        indicador_led.establecer_estado('grabando')
                        
                        # 2. Enviar cabeceras HTTP
                        conn.send('HTTP/1.1 200 OK\r\n'.encode('utf-8'))
                        conn.send('Content-Type: application/octet-stream\r\n'.encode('utf-8'))
                        conn.send('Connection: keep-alive\r\n'.encode('utf-8'))
                        conn.send('Cache-Control: no-cache\r\n\r\n'.encode('utf-8'))
                        
                        # Establecer timeout de 5.0 segundos en la conexión activa de streaming.
                        # Si el celular bloquea su pantalla o suspende el Wi-Fi, la llamada a conn.sendall()
                        # fallará por timeout en 5 segundos, liberando los recursos de inmediato!
                        conn.settimeout(5.0)
                        
                        print("[TCP] Cabeceras enviadas. Transmitiendo stream de audio...")
                        
                        try:
                            while captura_adc.streaming_active:
                                # Alimentar al Watchdog en cada bloque transmitido (cada 1s)
                                wdt.feed()
                                
                                # Esperar a que el Core 1 complete un bloque de 1.0 segundo (8000 muestras)
                                while not captura_adc.buffer_ready:
                                    if not captura_adc.streaming_active:
                                        break
                                    time.sleep_ms(10)
                                    
                                if not captura_adc.streaming_active:
                                    break
                                    
                                # Obtener el buffer listo
                                buf = captura_adc.obtener_buffer_listo()
                                
                                # Enviar el buffer signed 16-bit
                                conn.sendall(buf)
                                
                                # Ejecutar recolección de basura manual para liberar la memoria
                                # de los búferes TCP y objetos temporales de red en el Core 0.
                                # Ya que el búfer dura 1.0 segundo, el Core 0 tiene tiempo de sobra
                                # para hacer GC sin retrasar la digitalización en Core 1 (que no aloca).
                                gc.collect()
                                
                        except Exception as stream_err:
                            print(f"[TCP] Conexión cerrada o error de streaming: {stream_err}")
                        finally:
                            # Parar ADC, liberar RAM y regresar el LED a su modo habitual
                            captura_adc.detener_grabacion()
                            captura_adc.liberar_memoria()
                            indicador_led.establecer_estado('conectado')
                            print("[TCP] Streaming detenido y recursos liberados.")
                    else:
                        conn.send('HTTP/1.1 500 Internal Server Error\r\n\r\nFallo al iniciar adquisicion'.encode('utf-8'))
                
                # --- RUTA DE DEPURACIÓN PARA SIMULAR CUELGUE ---
                elif 'GET /debug_hang' in request:
                    print("[DEBUG] ⚠️ Simulando cuelgue de CPU. Watchdog reiniciará la Pico en 8s...")
                    while True:
                        pass
                
                # --- RUTA PRINCIPAL (WEB DAQ HTML) ---
                elif 'GET / ' in request or 'GET /?' in request:
                    print(f"[{addr[0]}] 🌐 Sirviendo dashboard web (index.html) en bloques...")
                    indicador_led.establecer_estado('conectado')
                    conn.send('HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n'.encode('utf-8'))
                    enviar_html_chunked(conn)
                
                else:
                    # Responder 404 a otras peticiones
                    conn.send('HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nNo encontrado'.encode('utf-8'))
                    
            except Exception as e:
                print(f"Error procesando solicitud HTTP: {e}")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
                gc.collect()
                
    except KeyboardInterrupt:
        s.close()
        print("\nServidor web detenido manualmente.")
