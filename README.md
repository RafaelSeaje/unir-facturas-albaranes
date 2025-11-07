# Unir-Facturas-Albaranes

Script en Python para unir facturas PDF con sus albaranes asociados.  
Permite procesar carpetas de facturas, buscar albaranes (incluso recursivamente en subcarpetas por quincenas/años), aplicar OCR cuando haga falta y generar PDFs combinados por factura.

---

## Estructura recomendada del repositorio

```
Unir-Facturas-Albaranes/
├── src/
│   └── "Unir facturas con albaranes.py"   # script principal
├── docs/
│   └── briefing.md
├── scripts/
│   └── build_exe.bat
├── .gitignore
└── README.md
```

---

## Prerrequisitos

- Windows 10/11 (o similar)  
- Python 3.10+ instalado y accesible desde la terminal (`python` en PATH)  
- Tesseract OCR instalado (si se desea OCR):  
  - Ruta típica: `C:\Program Files\Tesseract-OCR\tesseract.exe`  
  - Descargar: https://github.com/tesseract-ocr/tesseract/releases

---

## Dependencias Python (instalar en tu entorno)

Ejecutar en PowerShell o CMD:

```bash
python -m pip install --upgrade pip
python -m pip install PyMuPDF PyPDF2 pytesseract pillow pdf2image tqdm
```

> Nota: `PyMuPDF` se importa como `fitz` en los scripts.

---

## Ejecutar el script (modo desarrollo)

1. Abrir terminal en la raíz del repo.  
2. Ejecutar:

```bash
python src/"Unir facturas con albaranes.py"
```

3. El programa mostrará cuadros de diálogo para seleccionar:
   - Carpeta de facturas a procesar (p. ej. `C:\Archivo Digital\Bandeja de entrada\Facturas emitidas\2025\2025-10-2Q`)
   - Carpeta base de albaranes (p. ej. `C:\Archivo Digital\Bandeja de entrada\Albaranes emitidos\2025`) — se busca recursivamente en subcarpetas
   - Carpeta destino para las facturas procesadas (p. ej. `C:\Firma digital`)

4. El script genera un log (`logs.txt` o `procesa_facturas_log.txt`) en la carpeta del script con el detalle de la ejecución y el listado de albaranes no encontrados (si los hay).

---

## Compilar a .exe (PyInstaller)

Para crear un único ejecutable:

1. Desde la carpeta raíz del repo:

```bash
pyinstaller --onefile --name "Unir facturas con albaranes" src/"Unir facturas con albaranes.py"
```

2. El `.exe` resultante estará en `dist\Unir facturas con albaranes.exe`.  
3. Para depurar, ejecuta sin `--noconsole` (verás salida en consola). Para uso normal, puedes añadir `--noconsole`.

**Sugerencia**: crea un `scripts/build_exe.bat` con el comando anterior para reproducibilidad.

---

## Buenas prácticas

- No subir binarios grandes (`.exe`) al repositorio principal. Para compartir releases usa **GitHub Releases**.
- Mantén los PDFs de producción fuera del directorio del script (por ejemplo en `C:\Archivo Digital\...`) para evitar mezclas accidentales.
- Usa ramas (`feature/...`) para desarrollar cambios y abre Pull Requests para fusionarlos a `main`.

---

## .gitignore recomendado (ejemplo)

```
# Python
__pycache__/
*.py[cod]
*.pyo

# Virtual env
venv/
env/

# PyInstaller
dist/
build/
*.spec

# Logs
*.log
logs.txt
procesa_facturas_log.txt

# OS
.DS_Store
Thumbs.db
```

---

## Notas finales

- El script intenta extraer texto nativo primero; si no hay texto usa OCR (más lento).  
- El proceso está diseñado para **no bloquearse** en caso de archivos faltantes: registra warnings y continúa con las demás facturas.  
- Si necesitas que prepare el `README` en otro idioma o añada más instrucciones (por ejemplo, uso del `.exe`, automatización por tareas programadas o integración con GitHub Actions), dímelo y lo preparo paso a paso.

---
