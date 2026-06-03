import machine
import config
import red_wifi
import servidor_web
import indicador_led

def main():
    print("=========================================")
    print("  Receptor Web-DAQ SDR - INAUT (UNSJ)    ")
    print("=========================================")
    
    # 0. Overclocking seguro del microcontrolador a 150 MHz 
    # (Por defecto RP2040/RP2350 está a 125/150, forzamos 150MHz
    #  para garantizar que el WiFi TCP no interfiera con el Timer del ADC).
    machine.freq(150000000)
    
    # Activar parpadeo medio: alimentación conectada, buscando red/cliente
    indicador_led.establecer_estado('esperando')
    
    # 1. Levantar la red Wi-Fi
    ap, ip = red_wifi.configurar_ap(config.WIFI_SSID, config.WIFI_PASS, config.WIFI_IP)
    
    print(f"\n[INFO] 📱 Conéctate a la red Wi-Fi: '{config.WIFI_SSID}'")
    print(f"[INFO] 🌍 Abre en el navegador del celular: http://{ip}")
    print("-----------------------------------------")
    
    # 2. Entrar al loop infinito del servidor Web-DAQ
    servidor_web.iniciar_servidor(config.WEB_PORT)

if __name__ == '__main__':
    main()
