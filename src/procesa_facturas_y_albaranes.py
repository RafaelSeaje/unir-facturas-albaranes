
import os
import re
import sys
import fitz
import logging
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
        logging.StreamHandler(sys.stdout) if sys.stdout else logging.NullHandler()
    ]
)

# ==============================
# FUNCIONES AUXILIARES
# ==============================

def extraer_texto_pagina(pdf_path):
    try:
        with fitz.open(pdf_path) as doc:
            return doc[0].get_text("text")
    except Exception as e:
        logging.warning(f"No se pudo extraer texto de {pdf_path}: {e}")
        return ""

def extraer_bloques(pdf_path):
    try:
        with fitz.open(pdf_path) as doc:
            page = doc[0]
            return page.get_text("blocks")
    except Exception as e:
        logging.warning(f"No se pudieron extraer bloques de {pdf_path}: {e}")
        return []

def limpiar_nombre_cliente_raw(texto):
    texto = re.sub(r'[^A-ZÁÉÍÓÚÑÜ0-9\s\.-]', '', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

def extraer_nombre_cliente(pdf_path):
    try:
        blocks = extraer_bloques(pdf_path)
        if not blocks:
            return None

        with fitz.open(pdf_path) as doc:
            w, h = doc[0].rect.width, doc[0].rect.height

        candidates = [b for b in blocks if b[0] >= w * 0.45 and b[1] <= h * 0.30]
        candidates.sort(key=lambda b: (b[1], -b[0]))

        posibles_lineas = []
        for (_, _, _, _, texto) in candidates:
            for ln in texto.splitlines():
                ln = ln.strip()
                if ln:
                    posibles_lineas.append(ln)

        mayus = [l for l in posibles_lineas if l.isupper()]
        if len(mayus) >= 3:
            cliente_line = mayus[2]
        elif len(mayus) >= 1:
            cliente_line = mayus[-1]
        else:
            cliente_line = posibles_lineas[-1] if posibles_lineas else None

        if cliente_line:
            cliente_limpio = limpiar_nombre_cliente_raw(cliente_line)
            logging.info(f"Nombre de cliente detectado: {cliente_limpio}")
            return cliente_limpio
    except Exception as e:
        logging.warning(f"Error extrayendo cliente de {pdf_path}: {e}")
    return None

def buscar_albaran_primero(num, carpeta_base, usados_por_factura=None):
    if usados_por_factura is None:
        usados_por_factura = set()
    coincidencias = []
    for root, _, files in os.walk(carpeta_base):
        for f in files:
            if f.lower().endswith(".pdf") and re.search(rf"\b{re.escape(num)}\b", f):
                coincidencias.append(os.path.join(root, f))
    for c in coincidencias:
        if c not in usados_por_factura:
            return c
    return None

def unir_pdfs(pdf_principal, lista_pdf_albaranes, destino):
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
        "2️⃣ Carpeta base de albaranes (incluye subcarpetas)\n"
        "3️⃣ Carpeta destino para guardar las facturas completas."
    )

    messagebox.showinfo("Facturas", "Seleccione la carpeta que contiene las facturas a procesar.")
    carpeta_facturas = filedialog.askdirectory(title="Carpeta de facturas a procesar")

    messagebox.showinfo("Albaranes", "Seleccione la carpeta base donde buscar los albaranes.")
    carpeta_albaranes = filedialog.askdirectory(title="Carpeta base de albaranes")

    messagebox.showinfo("Destino", "Seleccione la carpeta donde se guardarán las facturas completas.")
    carpeta_destino = filedialog.askdirectory(title="Carpeta destino de facturas completas")

    if not carpeta_facturas or not carpeta_albaranes or not carpeta_destino:
        logging.error("No se seleccionaron todas las carpetas necesarias.")
        messagebox.showerror("Error", "No se seleccionaron todas las carpetas necesarias.")
        return

    archivos_facturas = [f for f in os.listdir(carpeta_facturas) if f.lower().endswith(".pdf")]
    logging.info(f"Facturas detectadas: {len(archivos_facturas)}")

    albaranes_faltantes, facturas_sin_unir, usados_global = [], [], set()
    disable_tqdm = not sys.stdout or not sys.stdout.isatty()

    for factura in tqdm(archivos_facturas, desc="Procesando facturas", ncols=80, disable=disable_tqdm):
        ruta_factura = os.path.join(carpeta_facturas, factura)
        texto = extraer_texto_pagina(ruta_factura)
        nums = re.findall(r"\b\d{3,6}\b", texto)
        nums = list(dict.fromkeys(nums))

        cliente = extraer_nombre_cliente(ruta_factura) or "CLIENTE"
        lista_a_unir, usados_factura = [], set()

        logging.info(f"\nFactura {factura}: números detectados {nums}")

        for num in nums:
            ruta_alb = buscar_albaran_primero(num, carpeta_albaranes, usados_factura)
            if ruta_alb:
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

    # RESUMEN FINAL
    logging.info("\n=== FIN DEL PROCESO ===")
    logging.info(f"Facturas procesadas: {len(archivos_facturas)}")

    if albaranes_faltantes:
        logging.info("Albaranes faltantes detectados:")
        for f, n in albaranes_faltantes:
            logging.info(f"  - Factura {f}: albarán {n}")

    if facturas_sin_unir:
        logging.info("Facturas sin albaranes:")
        for f in facturas_sin_unir:
            logging.info(f"  - {f}")

    todos_albaranes = []
    for root, _, files in os.walk(carpeta_albaranes):
        for f in files:
            if f.lower().endswith(".pdf"):
                todos_albaranes.append(os.path.join(root, f))

    no_usados = [a for a in todos_albaranes if a not in usados_global]
    if no_usados:
        logging.info("Albaranes no utilizados:")
        for a in no_usados:
            logging.info(f"  - {os.path.basename(a)}")

    logging.info(f"Log completo: {LOG_FILE}")
    messagebox.showinfo("Finalizado", "Proceso completado.\nRevise el log para más detalles.")

if __name__ == "__main__":
    main()
