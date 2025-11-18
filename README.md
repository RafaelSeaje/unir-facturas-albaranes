# 🧾 Unir  Facturas y Albaranes

Un programa sencillo para uso administrativo que permite **combinar automáticamente facturas  PDF con sus albaranes correspondientes**, generando un único archivo final por cada factura.  
Ideal para contables, administrativos o responsables de archivo digital que trabajan con facturas y albaranes en formato PDF.

---

## 🎯 ¿Para qué sirve?

Cuando una factura incluye uno o varios albaranes (documentos de entrega) que están en PDF por separado, este programa:

- Identifica el **número de factura** y el **nombre del cliente** que aparecen en la factura.  
- Extrae los números de los albaranes que figuran en la factura (por ejemplo: “Albarán Núm. A25  487 de 07/04/2025”).  
- Busca automáticamente esos albaranes en una carpeta — y en **subcarpetas también** —.  
- Une la factura + sus albaranes en un solo PDF con nombre claro (fecha, factura, cliente).  
- Genera un registro de actividad (log) con las facturas procesadas, los albaranes encontrados o no encontrados, y los resultados finales.

Esto permite tener un archivo único por factura, listo para archivar, firmar digitalmente o enviar al cliente.

---

## 📂 Estructura del repositorio

```
unir-facturas-albaranes/
├── src/                                  # Código fuente (.py)
│   └── unir_facturas_albaranes.py        # Script principal
├── dist/                                 # Ejecutables generados (.exe) cuando el script es compilado
├── logs/                                 # Carpetas de registros de ejecución
├── README.md                             # Este archivo: información del proyecto
└── LICENSE (opcional)                    # Licencia del proyecto
```

---

## ⚙️ Requisitos

### 🔧 Software

- Windows 10  o 11  
- Python 3.10 o superior (si usa el script `.py` directamente)  
  - Para usar como ejecutable `.exe` no se necesita saber Python.  
- (Opcional) PyInstaller, si desea generar su propio `.exe`.

### 📦 Librerías utilizadas y por qué

| Librería           | ¿Para qué se usa?                                                |
|---------------------|-----------------------------------------------------------------|
| `PyMuPDF` (alias `fitz`) | Permite abrir PDFs, extraer texto y bloques de texto (posiciones) para identificar nombres y albaranes. |
| `PyPDF2`             | Permite combinar varios PDFs (factura + albaranes) en un único archivo. |
| `tkinter`           | Proporciona ventanas gráficas para que el usuario seleccione las carpetas sin usar consola. |
| `tqdm`              | Proporciona barra de progreso cuando se ejecuta en consola (aunque en el `.exe` gráfico se suprime). |
| `logging`           | Registra en un archivo “log” todo el proceso: qué facturas, qué albaranes, qué errores. |

---

## 🚀 Instalación del script

Si desea usar el script directamente (.py):

1. Instale Python 3.10+ si aún no lo tiene.  
2. Descargue o clone este repositorio.  
3. Abra una terminal en la carpeta `src/`.  
4. Instale las dependencias:
   ```bash
   pip install PyMuPDF PyPDF2 tqdm
   ```
5. Ejecute:
   ```bash
   python unir_facturas_albaranes.py
   ```

### 🖥️ Si desea usarlo como ejecutable (.exe)

1. Instale PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. En la carpeta `src/`, ejecute:
   ```bash
   pyinstaller --onefile --noconsole "unir_facturas_albaranes.py"
   ```
3. Se generará el archivo `dist\unir_facturas_albaranes.exe`. Copie‑pegué ese `.exe` en la carpeta que desee y ejecútelo con doble‑clic.

---

## 🧾 Uso paso a paso (usuario no técnico)

1. Doble‑clic para abrir el programa (o ejecute al script).  
2. Aparecerá un mensaje explicativo. Luego se le pedirá que **seleccione tres carpetas**, en este orden:
   - Carpeta donde están **las facturas a procesar**.  
   - Carpeta base donde se encuentran **los albaranes** (puede contener subcarpetas).  
   - Carpeta de **destino**, donde desea que se guarden los PDFs combinados.  
3. El programa comenzará a procesar. Aparecerá al finalizar un mensaje “Proceso completado”.  
4. Abra la carpeta de destino: verá archivos con nombres tipo:  
   ```
   2025‑10‑31 FE#1106 NOMBRE_CLIENTE.pdf
   ```
5. Abra también la carpeta `logs` y verá el archivo `procesa_facturas_log.txt`, donde podrá revisar los detalles:  
   - Facturas procesadas.  
   - Albaranes encontrados o faltantes.  
   - Facturas sin albaranes o albaranes no usados.

---

## 🧠 Buenas prácticas para uso administrativo

- Asegúrese de que las facturas en la carpeta “facturas a procesar” ya estén **renombradas** en formato `AAAA‑MM‑DD FE#nnnn` seguido del cliente, **si ya fuera necesario** (el script añadirá el nombre del cliente si lo encuentra).  
- Verifique que la carpeta de albaranes incluya todos los archivos PDF de albaranes (por ejemplo, organizados por año o quincena). El script busca en subcarpetas automáticamente.  
- Una vez generado el archivo combinado, archive la factura original y los albaranes correspondientes si lo desea — el programa no los borra ni mueve por usted.  
- Revise el log al menos una vez al mes para detectar albaranes no encontrados o facturas sin albaranes — así podrá completar su archivo antes de enviarlo al archivo digital o firma.

---

## ✨ ¿Qué pasa “detrás de cámaras”?

1. El programa abre cada factura en PDF y extrae el **nombre del cliente**, mediante análisis de bloque de texto en la zona superior‑derecha del documento.  
2. Luego extrae del texto de la factura los números de albarán que figuran (por ejemplo “A25 1345”).  
3. Por cada número de albarán, busca en la carpeta de albaranes (y subcarpetas) el archivo PDF cuyo nombre contenga ese número.  
4. Crea un PDF nuevo que incorpora **primero la factura** y luego, en el orden detectado, **los albaranes**.  
5. Guarda ese PDF en la carpeta de destino y registra todo el proceso en el log.

---

## 🧪 Limitaciones conocidas

- Si el PDF de factura no está bien generado (por ejemplo, es un escaneo sin OCR), el reconocimiento del cliente o de los números de albarán puede fallar.  
- Si el nombre del cliente no está en la zona esperada (superior‑derecha) o está dividido en más de una línea, puede no detectarse correctamente — revise entonces el archivo final y modifique manualmente si es necesario.  
- Si varios albaranes tienen **exactamente el mismo número** o rutas idénticas, puede generarse un duplicado — revise el log para corregirlos.

---

## 📣 Colaboración y mejoras

Este proyecto lo desarrolla **Rafael Seaje** (contable y desarrollador de automatización).  
Si desea proponer mejoras, activar OCR para facturas escaneadas o integrar en un sistema de firma digital, puede **crear un “Issue”** en este repositorio.

---

## 📜 Licencia

Este proyecto es para **uso personal o interno**. Está permitido modificarlo según sus necesidades, **pero no se publica como producto comercial sin permiso del autor**.

---

### ✅ En resumen

Unir  Facturas  y  Albaranes es una herramienta creada para facilitar y automatizar el trabajo administrativo de combinar facturas y albaranes en formato PDF, con un proceso guiado, registros de actividad y buen nivel de autonomía para usuarios sin conocimientos profundos de programación.
