# Automatización de Facturas y Albaranes – ERP → PDF

Este proyecto proporciona un conjunto de herramientas diseñadas para automatizar el tratamiento documental de facturas y albaranes generados desde un ERP.  
Los módulos permiten:

1. Separar un PDF único que contiene varias facturas en PDFs individuales.  
2. Renombrar automáticamente los albaranes según su número y fecha.  
3. Unir cada factura con todos los albaranes que le corresponden (en desarrollo).  
4. Estructurar carpetas de trabajo de forma estándar y asistida.

El proyecto está orientado a entornos administrativos, con enfoque práctico, sin requerir conocimientos técnicos avanzados.

---

## Estado actual del proyecto

### 🟢 Módulos completados
- **separar_facturas.py**  
  Divide un PDF con múltiples facturas en PDFs individuales, agrupando las páginas de cada factura y asignando nombres estandarizados.  
  Usa OCR (Tesseract) para detectar número de factura y fecha en un recuadro fijo.

- **procesar_albaranes.py**  
  Renombra albaranes PDF según su número y fecha, siguiendo un patrón fijo basado en la lectura OCR de un recuadro estructurado.

### 🟡 Módulos en desarrollo
- **unir_facturas_albaranes.py**  
  Unirá cada factura con sus albaranes correspondientes.  
  El módulo está iniciado y contiene detección preliminar de números de factura y albaranes.  
  Será actualizado para asumir que la identificación de factura (número y fecha) ya la aporta el módulo `separar_facturas.py`.

### 🟡 Estructura del proyecto  
Conjunto de subcarpetas y convenciones de nombres para automatizar totalmente el flujo de ERP → PDFs → Carpetas → Fusionado.

---

## Estructura del repositorio

```
/ (raíz)
│
├─ README.md               ← este documento
├─ requirements.txt
├─ USAGE.md                ← instrucciones ampliadas (opcional)
│
├─ src/
│   ├─ separar_facturas.py
│   ├─ procesar_albaranes.py
│   └─ unir_facturas_albaranes.py
│
├─ logs/
│   └─ (generado automáticamente)
│
└─ dist/                   ← aquí se guardan los .exe generados
```

---

# Funcionamiento de cada módulo

## 1. separarar_facturas.py
**Objetivo:**  
Dado un único PDF exportado desde el ERP con todas las facturas (una por página o varias páginas por factura), divide y genera un PDF por factura.

**Características:**
- Detección del número de factura dentro del recuadro superior-izquierdo.
- Correcciones internas del OCR para evitar errores típicos (0/O, 1/I/l, S/5, Z/2…)
- Agrupación de páginas consecutivas que pertenecen a la misma factura.
- Nombres de salida con formato:
  ```
  YYYY-MM-DD FE#NNNN SERIE.pdf
  ```
- GUI completa con selección de archivo origen, carpeta destino y barra de progreso.

**Entrada:**  
Un PDF único (ej.: `2025-10-2Q FACTURAS.pdf`)

**Salida:**  
PDFs individuales en la carpeta destino.

---

## 2. procesar_albaranes.py
**Objetivo:**  
Renombrar los albaranes usando los datos del recuadro superior-izquierdo (Número, Fecha, Cliente).

**Características:**
- OCR preciso en coordenadas fijas.
- Nombres estandarizados.
- Limpieza automática de formatos.

---

## 3. unir_facturas_albaranes.py
**Objetivo:**  
Fusionar cada factura con todos sus albaranes relacionados.  
Este módulo:
- Localizará los albaranes pertenecientes a cada factura.
- Integrará en un único PDF la factura + sus albaranes.
- Usará la nomenclatura estándar establecida por los módulos anteriores.

**Estado:**  
Iniciado, pendiente de adaptación a la nueva lógica del separador de facturas.

---

# Requisitos

El proyecto requiere:

```
pymupdf>=1.24
pillow>=10.0
pytesseract>=0.3
pypdf>=4.0
```

Tesseract debe estar instalado manualmente en Windows:

Ruta recomendada:
```
C:\Program Files\Tesseract-OCR\tesseract.exe
```

---

# Instalación

1. Instalar Python 3.9+  
2. Instalar dependencias:

```
pip install -r requirements.txt
```

3. Asegurar la instalación de Tesseract OCR.

---

# Compilación a .exe (si se desea)

Ejemplo para `separar_facturas.py`:

```
pyinstaller --onefile --noconsole ^
  --add-data "logs;logs" ^
  --name "SepararFacturas" src/separar_facturas.py
```

El ejecutable aparece en `dist/`.

---

# Uso general (resumen)

### Módulo 1 – Separar facturas
1. Ejecutar el `.exe` o el `.py`  
2. Elegir PDF origen  
3. Elegir carpeta destino  
4. Pulsar “INICIAR SEPARACIÓN”

### Módulo 2 – Renombrar albaranes
1. Ejecutar el módulo  
2. Seleccionar carpeta con albaranes  
3. Procesar

### Módulo 3 – Unir facturas + albaranes (en desarrollo)

---

# Licencia
Pendiente de definir.
