
import os
import re
import fitz
import logging
import shutil
from tkinter import Tk, filedialog, messagebox
from tqdm import tqdm

# ==============================
# CONFIGURACIÓN DEL LOG
# ==============================
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "procesa_facturas_log.txt")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# ==============================
# FUNCIONES AUXILIARES
# ==============================

def extraer_texto_pagina(pdf_path):
    """Devuelve el texto de la primera página del PDF."""
    try:
        with fitz.open(pdf_path) as doc:
            return doc[0].get_text("text")
    except Exception as e:
        logging.warning(f"No se pudo extraer texto de {pdf_path}: {e}")
        return ""


def extraer_bloques(pdf_path):
    """Devuelve los bloques de texto (x0, y0, x1, y1, text) de la primera página."""
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
        blocks = page.get_text("blocks")
        return [(b[0], b[1], b[2], b[3], b[4]) for b in blocks]
    except Exception as e:
        logging.warning(f"No se pudieron extraer bloques de {pdf_path}: {e}")
        return []


def limpiar_nombre_cliente_raw(texto):
    texto = re.sub(r'[^A-ZÁÉÍÓÚÑÜ0-9\s\.-]', '', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto


def extraer_nombre_cliente(pdf_path):
    """
    Extrae el nombre del cliente de la factura según el patrón:
    - Zona superior derecha (45–100% ancho, 0–30% alto)
    - Se ignoran líneas 'FACTURA' y 'CLIENTE'
    - Se toma la siguiente línea en mayúsculas del bloque rectangular
    """
    try:
        blocks = extraer_bloques(pdf_path)
        if not blocks:
            return None

        with fitz.open(pdf_path) as doc:
            w, h = doc[0].rect.width, doc[0].rect.height

        # Filtrar zona superior derecha
        candidates = [b for b in blocks if b[0] >= w * 0.45 and b[1] <= h * 0.30]
        candidates.sort(key=lambda b: (b[1], -b[0]))  # arriba a abajo

        posibles_lineas = []
        for (_, _, _, _, texto) in candidates:
            for ln in texto.splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                posibles_lineas.append(ln)

        # Buscar la 2ª línea en mayúsculas tras "FACTURA"/"CLIENTE"
        mayus = [l for l in posibles_lineas if l.isupper()]
        if len(mayus) >= 3:
            # 1: FACTURA, 2: CLIENTE_, 3: NOMBRE CLIENTE
            cliente_line = mayus[2]
        elif len(mayus) >= 1:
            cliente_line = mayus[-1]
        else:
            cliente_line = posibles_lineas[-1] if posibles_lineas else None

        if cliente_line:
            cliente_limpio = limpiar_nombre_cliente_raw(cliente_line)
            logging.info(f"Nombre de cliente detectado en {os.path.basename(pdf_path)}: {cliente_limpio}")
            return cliente_limpio

    except Exception as e:
        logging.warning(f"Error extrayendo cliente de {pdf_path}: {e}")
    return None


def buscar_albaran_primero(num, carpeta_base, usados_por_factura=None):
    """Busca el albarán correspondiente al número (busca también en subcarpetas)."""
    if usados_por_factura is None:
        usados_por_factura = set()
    coincidencias = []
    for root, _, files in os.walk(carpeta_base):
        for f in files:
            if f.lower().endswith(".pdf") and re.search(rf"\b{re.escape(num)}\b", f):
                coincidencias.append(os.path.join(root, f))
    if not coincidencias:
        return None
    for c in coincidencias:
        if c not in usados_por_factura:
            return c
    return coincidencias[0]


def unir_pdfs(pdf_principal, lista_pdf_albaranes, destino):
    """Une la factura con los albaranes y guarda el resultado."""
    try:
        doc = fitz.open()
        for ruta in [pdf_principal] + lista_pdf_albaranes:
            with fitz.open(ruta) as m:
                doc.insert_pdf(m)
        doc.save(destino)
        doc.close()
        return True
    except Exception as e:
        logging.error(f"Error uniendo PDFs: {e}")
        return False


# ==============================
# FUNCIÓN PRINCIPAL
# ==============================

def main():
    logging.info("=== INICIO DEL PROCESO ===")

    Tk().withdraw()
    messagebox.showinfo(
        "Información general",
        "A continuación seleccionará tres carpetas:\n"
        "1️⃣ Facturas a procesar\n"
        "2️⃣ Carpeta base donde buscar los albaranes (se incluirán subcarpetas)\n"
        "3️⃣ Carpeta destino donde se guardarán las facturas completas."
    )

    messagebox.showinfo("Seleccionar carpeta de FACTURAS", "Seleccione la carpeta que contiene las facturas a procesar.")
    carpeta_facturas = filedialog.askdirectory(title="Carpeta de facturas a procesar")

    messagebox.showinfo("Seleccionar carpeta de ALBARANES", "Seleccione la carpeta base de los albaranes (se buscará también en subcarpetas).")
    carpeta_albaranes = filedialog.askdirectory(title="Carpeta base de albaranes")

    messagebox.showinfo("Seleccionar carpeta DESTINO", "Seleccione la carpeta donde se guardarán las facturas completas.")
    carpeta_destino = filedialog.askdirectory(title="Carpeta destino de facturas completas")

    if not carpeta_facturas or not carpeta_albaranes or not carpeta_destino:
        logging.error("No se seleccionaron todas las carpetas necesarias.")
        return

    archivos_facturas = [f for f in os.listdir(carpeta_facturas) if f.lower().endswith(".pdf")]
    logging.info(f"Facturas detectadas: {len(archivos_facturas)}")

    albaranes_faltantes = []
    usados_global = set()
    facturas_sin_unir = []

    for factura in tqdm(archivos_facturas, desc="Procesando facturas", ncols=80):
        ruta_factura = os.path.join(carpeta_facturas, factura)
        texto = extraer_texto_pagina(ruta_factura)

        # Buscar números de albarán (patrón típico)
        nums = re.findall(r"\b\d{3,6}\b", texto)
        nums = list(dict.fromkeys(nums))  # eliminar duplicados manteniendo orden

        cliente = extraer_nombre_cliente(ruta_factura) or "CLIENTE"
        lista_a_unir, usados_factura = [], set()

        logging.info(f"\nFactura {factura}: números detectados {nums}")

        for num in nums:
            ruta_alb = buscar_albaran_primero(num, carpeta_albaranes, usados_factura)
            if ruta_alb:
                if ruta_alb in usados_factura:
                    logging.warning(f"Duplicado potencial de albarán {num} en {factura}")
                lista_a_unir.append(ruta_alb)
                usados_factura.add(ruta_alb)
                usados_global.add(ruta_alb)
                logging.info(f"  ✓ Albarán {num} → {os.path.basename(ruta_alb)}")
            else:
                albaranes_faltantes.append((factura, num))
                logging.warning(f"  ✗ No se encontró albarán {num} para {factura}")

        if lista_a_unir:
            salida = os.path.join(carpeta_destino, f"{os.path.splitext(factura)[0]}_{cliente}.pdf")
            if unir_pdfs(ruta_factura, lista_a_unir, salida):
                logging.info(f"Factura completa generada: {os.path.basename(salida)} con {len(lista_a_unir)} albaranes")
        else:
            facturas_sin_unir.append(factura)
            logging.warning(f"No se unieron albaranes para {factura}")

    # ==============================
    # RESUMEN FINAL
    # ==============================
    logging.info("\n=== FIN DEL PROCESO ===")
    logging.info(f"Facturas procesadas: {len(archivos_facturas)}")
    if albaranes_faltantes:
        logging.info("Albaranes faltantes detectados:")
        for f, n in albaranes_faltantes:
            logging.info(f"  - Factura {f}: albarán {n}")
    if facturas_sin_unir:
        logging.info("Facturas sin ningún albarán unido:")
        for f in facturas_sin_unir:
            logging.info(f"  - {f}")

    # Albaranes sin uso
    todos_albaranes = []
    for root, _, files in os.walk(carpeta_albaranes):
        for f in files:
            if f.lower().endswith(".pdf"):
                todos_albaranes.append(os.path.join(root, f))
    no_usados = [a for a in todos_albaranes if a not in usados_global]
    if no_usados:
        logging.info("Albaranes no utilizados en ninguna factura:")
        for a in no_usados:
            logging.info(f"  - {os.path.basename(a)}")

    logging.info(f"Log completo: {LOG_FILE}")
    messagebox.showinfo("Finalizado", "Proceso completado.\nRevise el log para más detalles.")


if __name__ == "__main__":
    main()
