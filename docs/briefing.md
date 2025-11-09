# 🧾 Briefing técnico del proyecto “Unir Facturas con Albaranes”

## 📌 Contexto general

El proyecto **Unir Facturas con Albaranes** es una herramienta creada para automatizar el proceso administrativo de combinar facturas y sus correspondientes albaranes en archivos PDF únicos.  
Está desarrollado en **Python**, y se compila como un ejecutable `.exe` para uso directo en entornos **Windows 10/11** (aunque puede adaptarse a macOS).

El autor es **Rafael Seaje**, contable, que utiliza el programa como parte de su flujo de archivo digital documental, donde las facturas y albaranes provienen de un **ERP industrial** que genera los PDFs mediante **Microsoft Print to PDF**.

El propósito es **ahorrar tiempo y evitar errores manuales** al archivar, firmar y clasificar documentación contable y administrativa.

---

## 🧱 Funcionalidad actual (versión estable)

El ejecutable actual realiza tres fases principales:

### 1️⃣ Renombrado de albaranes
- Detecta el **número de albarán** en el contenido de cada PDF, con expresiones regulares del tipo:
  ```
  Albarán Num. A25 487 de 07/04/2025
  ```
- Si el nombre del archivo aún no contiene su número, lo renombra con el patrón:
  ```
  Albarán nº ZZZZ.pdf
  ```

### 2️⃣ Renombrado de facturas
- Las facturas ya llegan parcialmente renombradas con el formato:
  ```
  AAAA-MM-DD FE#XXXX.pdf
  ```
- El script lee el contenido del PDF para extraer el **nombre del cliente** (ubicado en la primera línea en mayúsculas dentro de un bloque rectangular en la parte superior derecha de la página).
- Limpia el nombre (elimina puntos, caracteres inválidos, y siglas como S.L. o S.A.).
- Renombra la factura en el formato final:
  ```
  AAAA-MM-DD FE#XXXX Cliente.pdf
  ```

### 3️⃣ Unión de facturas y albaranes
- Lee cada factura y localiza los números de albarán mencionados en su contenido.
- Busca esos albaranes en la carpeta designada (y subcarpetas).
- Une los archivos PDF correspondientes en el orden en que aparecen dentro del texto de la factura.
- Guarda el resultado en la carpeta de destino con el mismo nombre de la factura.

### 🧩 Detalles adicionales
- Se muestran mensajes de progreso (barra `tqdm`) o interfaz sin consola.
- Se genera un **log** con los resultados del proceso, avisando de:
  - Facturas procesadas correctamente.
  - Albaranes no encontrados.
  - Duplicados detectados.
- Los errores no interrumpen el proceso: las facturas sin albaranes válidos se saltan y se registran en el log.

---

## 🗂️ Estructura de carpetas típica

```
C:\
 ├── Archivo Digital\
 │    ├── Bandeja de entrada\
 │    │    ├── Facturas emitidas\2025\2025-10-2Q\
 │    │    └── Albaranes emitidos\2025\2025-10-2Q\
 │    └── Firma digital\
 ├── Scripts\
 │    └── Unir facturas con albaranes\
 │         ├── unir_facturas_albaranes.py
 │         ├── dist\
 │         │    ├── unir_facturas_albaranes.exe
 │         │    └── logs\
 │         └── build\
 └── pruebas\
      └── v.02\
```

El `.exe` se aloja normalmente en:  
`C:\Scripts\Unir facturas con albaranes\dist\unir_facturas_albaranes.exe`

---

## 🧰 Tecnologías y dependencias

| Librería | Uso principal | Comentario |
|-----------|----------------|-------------|
| **PyMuPDF (`fitz`)** | Lectura de PDFs, extracción de texto y páginas | Preciso para procesar PDFs generados digitalmente o escaneados. |
| **PyPDF2** | Escritura, combinación y manipulación de PDFs | Permite unir las páginas de facturas y albaranes. |
| **tqdm** | Barra de progreso y seguimiento visual | Desactivada en versiones sin consola. |
| **tkinter** | Interfaz de selección de carpetas | Proporciona ventanas nativas de explorador de archivos. |
| **pytesseract (opcional)** | OCR para reconocimiento de texto en PDFs escaneados | Solo se activa si el texto no puede extraerse directamente. |
| **logging** | Registro de actividad y errores | Guarda el log de proceso (idealmente en `dist/logs`). |

---

## ⚙️ Estado actual del proyecto

✅ **Funciona correctamente:**
- Detecta y renombra albaranes.
- Renombra facturas con cliente (aunque con errores puntuales).
- Une PDFs en el orden correcto.
- Genera archivos finales en la carpeta destino.

⚠️ **Pendiente de mejora:**
1. Reconocimiento del **nombre del cliente** (detecta la palabra “CLIENTE” o “FACTURA” en lugar del nombre real).
2. Generación del archivo **log** en la ruta correcta (`dist/logs` o configurable).
3. Validar que el orden de albaranes se mantenga incluso en facturas largas.
4. Mejorar la claridad de las ventanas de selección de carpetas (mensajes antes de cada diálogo).
5. Optimizar tiempos de procesamiento (evitar bloqueos si falta un albarán).

---

## 🔒 Mejoras planificadas (issues abiertos o a crear)

### 1️⃣ Integrar firma digital con certificado FNMT
- Usar librería **PyHanko** para firma PAdES visible o invisible.
- Permitir configuración del certificado y contraseña.
- Registrar en el log cada factura firmada correctamente.

### 2️⃣ Procesar facturas no renombradas aún
- Detectar número y fecha de factura directamente en el PDF.
- Renombrar automáticamente según patrón estándar.
- Permitir OCR de respaldo si no se detecta texto.

### 3️⃣ Validaciones extra
- Informar en el log si:
  - Una factura no tiene albaranes asociados.
  - Un albarán no fue vinculado a ninguna factura.

---

## 🧩 Organización del repositorio (GitHub)

Repositorio:  
🔗 [https://github.com/RafaelSeaje/unir-facturas-albaranes](https://github.com/RafaelSeaje/unir-facturas-albaranes)

**Estructura recomendada:**
```
unir-facturas-albaranes/
├── src/
│   └── unir_facturas_albaranes.py
├── docs/
│   ├── README.md
│   └── briefing.md
├── dist/
│   └── unir_facturas_albaranes.exe
├── logs/
├── tests/
├── requirements.txt
└── .gitignore
```

**Ramas:**
- `main`: versión estable.
- `dev`: rama de trabajo para nuevas versiones o pruebas.

---

## 🧩 Etiquetas (labels) recomendadas para GitHub Issues

| Nombre | Color | Descripción |
|--------|--------|-------------|
| `enhancement` | 🟢 #28a745 | Mejora o nueva funcionalidad. |
| `bug` | 🔴 #d73a4a | Error o fallo. |
| `future-feature` | 🟣 #a371f7 | Mejora planificada. |
| `documentation` | 🟡 #f9d67a | Cambios en documentación. |
| `question` | 🔵 #3b88fd | Duda o debate previo a cambio. |
| `refactor` | ⚫ #6e7781 | Reestructuración interna del código. |
| `performance` | 🟠 #fc9d03 | Mejora de rendimiento. |
| `duplicate` | ⚪ #cccccc | Issue duplicado. |
| `good first issue` | 🩵 #7057ff | Ideal para nuevos colaboradores. |
| `help wanted` | 🟢 #008672 | Se necesita ayuda o revisión. |
| `invalid` | ⚫ #6e7781 | Issue no válido o irreproducible. |
| `wontfix` | 🔴 #d73a4a | No se corregirá. |

---

## 🧭 Próximos pasos recomendados

1. **Resolver la extracción del nombre del cliente** por coordenadas o OCR selectivo.  
2. **Asegurar la creación del log** en ruta estable.  
3. **Incorporar el control de duplicados de albaranes** en cada factura.  
4. **Integrar firma digital FNMT** como nueva fase (posterior a la unión).  
5. **Publicar una versión `v0.3`** en GitHub (rama `dev` → merge a `main`).

---

## 📚 Créditos y licencias

**Autor:** Rafael Seaje  
**Asistente técnico:** ChatGPT (OpenAI)  
**Lenguaje:** Python 3.11+  
**Licencia:** MIT (por confirmar o añadir al repositorio)

---

*Documento actualizado a noviembre de 2025.  
Sirve como referencia técnica y operativa para la continuidad del desarrollo del proyecto.*
