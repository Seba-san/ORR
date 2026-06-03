import network
import time

def configurar_ap(ssid, password, ip_estatica='192.168.4.1'):
    """
    Configura y activa el Punto de Acceso (AP) Wi-Fi en la Raspberry Pi Pico con una IP fija.
    """
    print(f"Iniciando Punto de Acceso Wi-Fi ({ssid})...")
    ap = network.WLAN(network.AP_IF)
    
    # Configurar SSID y Contraseña
    ap.config(essid=ssid, password=password)
    
    # Forzar la IP estática (IP, máscara de subred, puerta de enlace, DNS)
    ap.ifconfig((ip_estatica, '255.255.255.0', ip_estatica, '8.8.8.8'))
    
    ap.active(True)
    
    # Esperar a que el AP esté activo
    while not ap.active():
        time.sleep(0.1)
        
    ip = ap.ifconfig()[0]
    print(f"✅ Punto de acceso activo. IP: {ip}")
    return ap, ip
