# 🖨️ Gabinete Mecánico 3D y Acoplamiento

Este directorio está reservado para los modelos tridimensionales (archivos `.stl`, `.step` / `.stp`) de la carcasa de protección y acople mecánico del módem ORR con la radio Baofeng UV-82.

---

## 🛠️ Características de Diseño

El diseño del gabinete ha sido desarrollado considerando las condiciones de vibración y humedad del trabajo agrícola en el campo:

1. **Dimensiones Extendidas:** La carcasa se ha alargado físicamente para alojar de forma holgada tanto la placa transmisora (TX) como la receptora (RX) con sus componentes discretos. Esto evita tensiones mecánicas internas o desprendimiento de soldaduras.
2. **Protector de Pestillo de Batería:** Se integran encastres y ranuras protectoras para el botón de liberación de la batería del Baofeng UV-82. Esto previene que el módulo digital presione accidentalmente el mecanismo de eyección y provoque que la batería se desprenda ante sacudidas o golpes en tractores agrícolas.
3. **Puntos de Alivio de Tensión:** Cuenta con pasacables con curvas diseñadas para evitar fatiga en los conectores de audio de 3.5 mm y 2.5 mm.

---

## ⚙️ Parámetros de Impresión Recomendados

Para garantizar la durabilidad a la intemperie y resistencia a la radiación solar en cultivos agrícolas, se sugieren los siguientes parámetros:

* **Material:** **PETG** o **ABS** (se desaconseja el uso de PLA debido a su baja tolerancia térmica ante la exposición solar directa en el campo).
* **Altura de Capa:** $0.2\text{ mm}$ o $0.15\text{ mm}$ para un encastre preciso.
* **Relleno (Infill):** $25\text{ a } 35\%$ con patrón giroidal (*gyroid*) o rejilla para maximizar la resistencia a impactos.
* **Perímetros (Muros):** Mínimo 3 de espesor.
* **Soportes:** No requiere soportes si se orienta de forma plana sobre la base (según el diseño de encastres).

---

## 📂 Archivos de Diseño 3D en esta carpeta

Este directorio contiene las piezas del diseño final de la carcasa, listas para imprimir o editar:

*   **[base_v4-carcasa.stl](./base_v4-carcasa.stl)**: Pieza principal del gabinete de protección (carcasa).
*   **[base_v3-base_con_placa.stl](./base_v3-base_con_placa.stl)**: Base de acoplamiento que sostiene mecánicamente la electrónica y las placas.
*   **[lengueta.stl](./lengueta.stl)**: Pestillo o lengüeta de traba para fijar el ensamble al seguro de la radio.
*   **[base_v4.FCStd](./base_v4.FCStd)**: Archivo de diseño paramétrico original creado en **FreeCAD** (herramienta de CAD de código abierto). Contiene todo el historial de modelado para realizar modificaciones, redimensionados o adaptaciones futuras.

