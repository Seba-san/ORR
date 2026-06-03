"""
evaluador.py — Evaluador de Tasa de Error de Bit (BER) y Análisis Temporal
============================================================================
Proyecto : Comunicación Digital sobre Radios Analógicas FM (JAR 2026)
Instituto: Instituto de Automática (INAUT) — UNSJ — CONICET

Implementa el cálculo de la Tasa de Error de Bit (BER) comparando bit a bit los
datos demodulados con el patrón PRBS-7 original generado por LFSR.
Utiliza correlación cruzada temporal para autoalinear las secuencias y compensar
el delay de grupo de los filtros y el retardo analógico del canal de RF.
============================================================================
"""

import numpy as np
import os
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Asegurar importación de config y LFSR
sys.path.insert(0, os.path.dirname(__file__))
import config
# Agregar temporalmente firmware/tx para importar LFSR
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'firmware', 'tx')))
from lfsr import LFSR
sys.path.pop(0)  # Limpiar sys.path


class EvaluadorBER:
    """
    Evaluador matemático de BER con alineación automática por correlación cruzada.
    """

    def __init__(self, seed=None):
        self._seed = seed if seed is not None else config.PRBS7_SEED
        # Instanciar el LFSR de referencia
        self.lfsr = LFSR(seed=self._seed)
        # Generar ciclo base de 127 bits de referencia
        self.patron_base = self.lfsr.generate_sequence()

    def alinear_secuencia(self, bits_demodulados):
        """
        Encuentra el desfase temporal óptimo (offset de bit) mediante la maximización
        de coincidencias cíclicas con el patrón de referencia PRBS-7.
        """
        n_demod = len(bits_demodulados)
        if n_demod == 0:
            return 0, 1.0, []

        L = len(self.patron_base)  # 127
        coincidencias = []

        # Buscamos el offset circular (0 a 126) que maximiza los aciertos
        for offset in range(L):
            coincide = 0
            for i in range(n_demod):
                bit_ref = self.patron_base[(i + offset) % L]
                if bits_demodulados[i] == bit_ref:
                    coincide += 1
            coincidencias.append(coincide)

        # El offset óptimo es el que maximiza las coincidencias
        offset_optimo = np.argmax(coincidencias)
        max_aciertos = coincidencias[offset_optimo]
        precision_alineacion = max_aciertos / n_demod

        # Construir la secuencia de referencia alineada de longitud n_demod
        secuencia_referencia = [self.patron_base[(i + offset_optimo) % L] for i in range(n_demod)]

        if config.MODO_VERBOSE:
            print(f"[EvaluadorBER] Alineación completa por correlación circular:")
            print(f"  Offset de fase óptimo : {offset_optimo} bits")
            print(f"  Coincidencias máximas : {max_aciertos} de {n_demod} bits ({precision_alineacion*100.0:.2f}%)")

        return offset_optimo, precision_alineacion, secuencia_referencia

    def calcular_ber(self, bits_demodulados):
        """
        Calcula la Tasa de Error de Bit (BER) real y la distribución temporal de errores.

        Args:
            bits_demodulados (list[int]): Lista de bits demodulados por la cadena del receptor.

        Returns:
            dict: {
                'ber': float (0.0 a 1.0),
                'total_bits': int,
                'bits_erroneos': int,
                'vector_errores': np.ndarray (1 si hay error, 0 si es correcto),
                'secuencia_referencia': list[int]
            }
        """
        n_demod = len(bits_demodulados)
        if n_demod == 0:
            return {'ber': 1.0, 'total_bits': 0, 'bits_erroneos': 0, 'vector_errores': np.array([]), 'secuencia_referencia': []}

        # 1. Alinear temporalmente
        offset, precision, sec_ref = self.alinear_secuencia(bits_demodulados)

        # 2. Comparar bit a bit
        vector_errores = np.zeros(n_demod, dtype=int)
        bits_erroneos = 0

        for i in range(n_demod):
            if bits_demodulados[i] != sec_ref[i]:
                vector_errores[i] = 1
                bits_erroneos += 1

        ber = bits_erroneos / n_demod

        return {
            'ber': ber,
            'total_bits': n_demod,
            'bits_erroneos': bits_erroneos,
            'vector_errores': vector_errores,
            'secuencia_referencia': sec_ref
        }

    def calcular_ber_segmento(self, bits_demodulados, bit_index_offset):
        """
        Calcula el BER para un segmento parcial alineado circularmente
        basándose en el patrón PRBS-7 de referencia a partir de una posición circular supuesta.
        """
        n_demod = len(bits_demodulados)
        if n_demod == 0:
            return {'ber': 1.0, 'bits_erroneos': 0}
            
        L = len(self.patron_base)
        # Buscamos el mejor offset para este segmento particular
        coincidencias = []
        for offset in range(L):
            coincide = 0
            for i in range(n_demod):
                bit_ref = self.patron_base[(i + offset) % L]
                if bits_demodulados[i] == bit_ref:
                    coincide += 1
            coincidencias.append(coincide)
            
        offset_opt = np.argmax(coincidencias)
        max_aciertos = coincidencias[offset_opt]
        bits_err = n_demod - max_aciertos
        
        return {
            'ber': bits_err / n_demod,
            'bits_erroneos': bits_err
        }

    def graficar_perfil_errores(self, alias, res_ber, dir_salida):
        """
        Genera el gráfico premium perfil_error_temporal.png mostrando la distribución
        temporal de los errores a lo largo del tiempo de la ráfaga.
        """
        vector_err = res_ber['vector_errores']
        total_bits = res_ber['total_bits']
        ber = res_ber['ber']
        
        plt.figure(figsize=(11, 4))
        
        # Dibujar marcas rojas en los instantes donde ocurrieron errores
        indices_error = np.where(vector_err == 1)[0]
        
        plt.plot(np.arange(total_bits), np.zeros(total_bits), color='#27ae60', alpha=0.5, label='Bits Correctos')
        if len(indices_error) > 0:
            plt.vlines(indices_error, ymin=0, ymax=1.0, colors='#e74c3c', alpha=0.6, label='Bits con Error')
            
        plt.title(f"Distribución Temporal de Errores de Bit (Perfil de Ráfaga) - {alias}", fontweight='bold')
        plt.xlabel("Índice de Bit Transmitido")
        plt.ylabel("Estado de Decisión [0 = Correcto, 1 = Error]")
        plt.ylim(-0.15, 1.15)
        plt.legend(loc='upper right')
        
        # Texto con métricas
        plt.text(total_bits * 0.02, 0.4, f"BER Global = {ber*100.0:.4f}% ({res_ber['bits_erroneos']}/{total_bits} bits erróneos)", 
                 bbox=dict(facecolor='white', alpha=0.8, edgecolor='#34495e'), fontsize=10, fontweight='bold')
        
        os.makedirs(dir_salida, exist_ok=True)
        ruta_salida = os.path.join(dir_salida, f"perfil_error_temporal_{alias}.png")
        plt.savefig(ruta_salida, dpi=150)
        plt.close()
        
        print(f"[EvaluadorBER] Gráfico de perfil de error guardado en: {ruta_salida}")
        return ruta_salida
