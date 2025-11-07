# Briefing: "Unir facturas con albaranes"

**Propósito:**
Documento de referencia para subir al repositorio GitHub y continuar el desarrollo del ejecutable *Unir facturas con albaranes*. Contiene objetivos, requisitos funcionales y no funcionales, dependencias, flujo de trabajo esperado, estructura de repositorio, pasos para compilación y pruebas, y listas de verificación para los siguientes hitos.

---

## 1. Resumen ejecutivo

Se dispone de un ejecutable Python que procesa lotes de facturas (PDF) provenientes de un ERP y, para cada factura, busca los albaranes asociados (PDF) y genera un PDF final que contiene la factura seguida de los albaranes correlacionados. El sistema ya cuenta con una versión funcional probada en una carpeta de pruebas; se necesita organizar el código en un repositorio, documentarlo y aplicar mejoras pendientes (búsqueda recursiva en quincenas, inclusión del nombre del cliente en el PDF final, listado final de albaranes faltantes, robustez frente a PDFs sin texto —OCR— y rendimiento).

---

## 2. Objetivos del proyecto

- Crear un repositorio mantenible en GitHub con la última versión funcional del script y binarios de prueba.
- Asegurar que el ejecutable pueda instalarse y ejecutarse desde la carpeta definitiva: `C:\Scripts\Unir facturas con albaranes`.
- Implementar y verificar: búsqueda recursiva de albaranes en la carpeta de año + subcarpetas (quincenas), inclusión del nombre del cliente en el nombre del PDF final, listado consolidado de albaranes faltantes, y evitar bloqueos/atascos (timeouts razonables en operaciones pesadas de OCR).
- Proveer documentación clara para desarrollo futuro y para uso por parte del usuario administrativo.

---

## 3. Alcance y requisitos

### 3.1 Requisitos funcionales

1. El script/exe debe pedir tres carpetas al usuario (vía diálogo):
   - Carpeta de facturas a procesar (ej. `...\Facturas emitidas\2025\2025-10-2Q`).
   - Carpeta base de albaranes (ej. `...\Albaranes emitidos\2025`). Debe buscar en esa carpeta y en todas sus subcarpetas.
   - Carpeta de destino para los PDFs combinados (ej. `C:\Firma digital`).

2. Para cada factura:
   - Extraer los números de albarán listados en su texto (formato aproximado: `Albarán Num. A25  487  de 07/04/2025`).
   - Para cada número detectado, buscar el PDF de albarán correspondiente **recursivamente** en la carpeta de albaranes.
   - Si no se encuentra por nombre, opcionalmente buscar en el contenido del PDF (texto nativo o por OCR) —esto será configurable.
   - Generar un PDF combinado con la factura y los albaranes encontrados, y guardarlo en la carpeta de destino, manteniendo el nombre base de la factura y completando el nombre del cliente (extraído del propio PDF de la factura) si procede.

3. Al finalizar, generar en el log un resumen de los albaranes **no encontrados** (lista consolidada y única).

4. El programa debe continuar si encuentra errores con archivos individuales; no debe abortar el lote completo por un fallo puntual.

### 3.2 Requisitos no funcionales

- Interfaz de usuario: diálogos `tkinter` para selección de carpetas y mensajes finales. El exe debe poder ejecutarse por doble clic.
- Logging: `logs.txt` (o `procesa_facturas_log.txt`) en la carpeta del ejecutable; sobrescribir cada ejecución.
- Rendimiento: minimizar OCR (solo aplicar cuando la página/factura no contiene texto seleccionable); búsqueda por nombre antes de búsqueda por contenido; timeout configurable por albarán si se requiere.
- Robustez: manejo de excepciones por archivo, limpieza de recursos, y no bloques de GUI.

---

## 4. Dependencias (versión mínima recomendada)

- Python 3.10+ (preferible 3.11) o entorno virtual equivalentes.
- PyMuPDF (`fitz`) — lectura rápida de PDF y renderizado de páginas a imagen.
- PyPDF2 — manipulación (unión) de PDFs.
- pytesseract — wrapper de Tesseract OCR (requiere instalación de Tesseract en Windows, típicamente en `C:\Program Files\Tesseract-OCR\tesseract.exe`).
- pillow — para trabajar con imágenes.
- pdf2image — opcional para conversiones (si se prefiere frente a PyMuPDF para OCR).
- tqdm — solo para desarrollo / CMD; la versión distribuida con `--noconsole` evita usar `tqdm` en UI.

> Nota: Las librerías se instalan globalmente con pip; no dependen de la ubicación del script. Al compilar con PyInstaller, las dependencias necesarias se empaquetan para el exe.

---

## 5. Estructura de repositorio sugerida (GitHub)

```
unir-facturas-albaranes/
├── README.md
├── LICENSE
├── .gitignore
├── src/
│   └── procesa_facturas_y_albaranes.py     # script principal (modularizar después)
├── dist/                                   # binarios de prueba (no necesario en VCS, opcional)
├── tests/
│   └── sample_files/                        # PDFs de prueba (pequeños, con datos sanitizados)
├── docs/
│   └── briefing.md                          # este documento
└── scripts/
    └── build_exe.bat                        # comando pyinstaller reproducible
```

**Consejo:** Evitar subir PDFs con datos reales. Incluir en tests solo PDFs anonimizados o de ejemplo.

---

## 6. Propuesta de modularización del código (futuro)

- `io_utils.py` — funciones de selección de carpetas, creación de directorios y paths.
- `pdf_utils.py` — funciones de extracción de texto, OCR fallback, renderizado de páginas.
- `match_utils.py` — lógica de extracción de números y búsqueda/heurística de coincidencia de archivos.
- `renamer.py` — renombrado de albaranes y facturas.
- `merge.py` — operaciones de unión y escritura de PDFs.
- `cli.py` / `gui.py` — entrada principal y GUI/diálogos.

Modularizar facilita pruebas unitarias y la integración continua.

---

## 7. Instrucciones para compilar el `.exe` (reproducible)

1. Crear/usar un entorno virtual (opcional pero recomendado):
   ```bash
   python -m venv venv
   venv\Scripts\activate    # Windows
   pip install -U pip
   pip install PyMuPDF PyPDF2 pytesseract pillow pdf2image tqdm
   ```

2. Probar el script en el intérprete (sanity check):
   ```bash
   python src\procesa_facturas_y_albaranes.py
   ```

3. Compilar con PyInstaller desde la carpeta raíz del repo:
   ```bash
   pyinstaller --onefile --name "Unir facturas con albaranes" src\procesa_facturas_y_albaranes.py
   ```

4. Resultado: `dist\Unir facturas con albaranes.exe` — copiar a `C:\Scripts\Unir facturas con albaranes`.

> Para debugging inicial, compilar **sin** `--noconsole` y ejecutarlo desde CMD para ver mensajes en la consola.

---

## 8. Pruebas y validación

- **Prueba funcional:** usar la copia de pruebas que funciona (proporcionada) y verificar que se obtienen los mismos resultados.
- **Prueba de regresión:** modificar una factura para que falte su albarán y verificar que se registra en el log como faltante sin detener el proceso.
- **Prueba OCR:** tomar PDFs que solo contengan imágenes y validar que se detectan los números de albarán.
- **Prueba recursiva:** colocar albaranes en subcarpetas de distintas quincenas y verificar que se encuentran.

Registrar resultados en `tests/RESULTS.md`.

---

## 9. Issues abiertos (prioritarios)

1. **Incluir nombre del cliente en el nombre del PDF final** — corregir extracción y uso cuando se crea el PDF destino.
2. **Búsqueda recursiva por quincena** — asegurar que la búsqueda cubre carpeta del año y todas las quincenas.
3. **Mejorar rendimiento en carpetas grandes** — optimizar la lista de archivos de albaranes (indexar nombres una vez por ejecución, evitar OCR global).
4. **Timeout configurables** — para OCR en búsqueda por contenido (evitar bloqueos prolongados).
5. **Agregar CSV/JSON resumen** con mapping factura → albaranes encontrados → faltantes (útil para auditoría).

---

## 10. Archivos entregados como referencia (estado actual)

- Última versión del script que ha funcionado en la carpeta de pruebas: `procesa_facturas_y_albaranes.py`.
- Registro de la ejecución de prueba con 63 facturas: `procesa_facturas_log.txt`.

*(Estos archivos han sido subidos por el usuario y contarán como punto de partida para el repo).*

---

## 11. Siguientes pasos recomendados (prioridad)

1. Subir el repo con la estructura propuesta y añadir este briefing como `docs/briefing.md`.
2. Subir la versión funcional actual a `src/` y crear la rama `baseline` que represente el estado de trabajo que funciona.
3. Crear una rama `feature/fix-client-name-and-recursive-search` para las correcciones 1 y 2 de la sección "Issues abiertos".
4. Implementar tests pequeños con 3‑5 PDFs de ejemplo (anonimizados) que cubran: factura con 1 albarán, factura con varios albaranes, factura con albarán faltante, PDF sin texto.
5. Revisar el proceso de creación del `.exe` en la carpeta definitiva y documentar el comando `pyinstaller` en `scripts/build_exe.bat`.

---

## 12. Contacto y notas finales

Cuando subas el repo, comparte el enlace y desde ahí puedo:

- Crear PRs con los cambios propuestos (incluida la corrección para incluir el nombre del cliente y búsqueda recursiva).  
- Preparar un pipeline simple de GitHub Actions que: ejecute tests (si están disponibles) y valide que el script corre (en entorno Windows-libre de GUI — se puede hacer test en Windows Server runner).  


---

*Documento generado para facilitar la transferencia del desarrollo del ejecutable a un repositorio GitHub y para que otro desarrollador (o tú mismo) continúe el trabajo con todos los requisitos y contexto claros.*

