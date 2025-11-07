
# -*- coding: utf-8 -*-
"""
unir_facturas_albaranes.py
Versión corregida: extracción robusta del nombre del cliente (bloque superior-derecha),
preservación del orden de los albaranes, logging fiable y mensaje/abrir log al final.
"""
import os
import re
import sys
import logging
import fitz                      # PyMuPDF
from PyPDF2 import PdfReader, PdfWriter
from tkinter import Tk, filedialog, messagebox
import io
from PIL import Image

# -------------------------
# PATHS y LOG (robusto)
# -------------------------
def app_base_dir():
    """
    Devuelve la carpeta base donde guardar logs:
    - Si estamos 'frozen' (exe PyInstaller): dirname(sys.executable)
    - Si no, dirname(__file__)
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = app_base_dir()
LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOGS_DIR, "procesa_facturas_log.txt")

# Configurar logging
logging.basicConfig(
    filename=LOG_FILE,
    filemode="w",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# También emitimos a consola si existe (útil en modo desarrollo)
console_handler = logging.StreamHandler(sys.stdout) if hasattr(sys, "stdout") and sys.stdout else None
if console_handler:
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(formatter)
    logging.getLogger().addHandler(console_handler)


# -------------------------
# UTILIDADES PDF / TEXTO
# -------------------------
def extraer_bloques_pymupdf_first_page(pdf_path):
    """
    Devuelve una lista de bloques (x0,y0,x1,y1, texto) de la primera página
    usando PyMuPDF, en el orden en que aparecen.
    """
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
        blocks = page.get_text("blocks")  # [(x0, y0, x1, y1, "text", block_no, ...), ...]
        # Convertimos a lista de (bbox, text)
        return [(b[0], b[1], b[2], b[3], b[4].strip()) for b in blocks if b[4].strip()]
    except Exception as e:
        logging.warning(f"extraer_bloques_pymupdf_first_page fallo en {os.path.basename(pdf_path)}: {e}")
        return []

def limpiar_nombre_cliente_raw(nombre):
    """Limpia sufijos y caracteres no deseados."""
    if not nombre:
        return None
    nombre = nombre.strip().replace('.', '')
    nombre = re.sub(r'\b(SL|SA|SLU|SLL|SCOOP|SCOOPG|SC)\b', '', nombre, flags=re.IGNORECASE)
    nombre = re.sub(r'\s{2,}', ' ', nombre).strip()
    nombre = re.sub(r'[\/\\\:\*\?\"\<\>\|]', '_', nombre)
    return nombre if nombre else None

def extraer_nombre_cliente(pdf_path):
    """
    Intentar localizar el recuadro superior-derecho y tomar la primera linea de ese bloque.
    Heurística:
      - obtener bloques de texto de la primera página
      - calcular width/height de la página y seleccionar bloques cuya x0 esté en la mitad derecha
        y cuyo y0 esté dentro del top 25% de la página (ajustable)
      - si hay varios bloques en esa zona, escoger el que tenga más líneas y tomar la primera línea no-vacía
    Fallback: buscar primeras líneas MAYÚSCULAS en toda la primera página (como última opción).
    """
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
        page_rect = page.rect  # tiene width y height
        w = page_rect.width
        h = page_rect.height

        blocks = extraer_bloques_pymupdf_first_page(pdf_path)
        # seleccionar bloques en la zona "top-right"
        candidates = []
        for (x0, y0, x1, y1, text) in blocks:
            # condiciones: x0 bastante a la derecha y y0 cerca del top
            if x0 >= w * 0.45 and y0 <= h * 0.30:
                candidates.append((x0, y0, x1, y1, text))

        # ordenar por y0 (de arriba a abajo) y por x0 (derecha primero)
        candidates.sort(key=lambda b: (b[1], -b[0]))

        # tomar la primera linea de texto del primer candidato que tenga texto
        for c in candidates:
            text = c[4]
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            if lines:
                # normalmente la primera linea en el recuadro es el nombre del cliente
                nombre = limpiar_nombre_cliente_raw(lines[0])
                if nombre and nombre.upper() != "FACTURA":
                    return nombre

        # fallback 1: si no hay candidatos suficientes, revisar bloques en todo el top area
        # buscar la primera línea mayúscula en la parte superior de la página
        for (x0, y0, x1, y1, text) in blocks:
            if y0 <= h * 0.35:
                for ln in text.splitlines():
                    ln = ln.strip()
                    if ln and ln.isupper() and len(ln) > 3 and ln.upper() != "FACTURA":
                        nombre = limpiar_nombre_cliente_raw(ln)
                        if nombre:
                            return nombre

        # fallback 2: buscar en toda la primera página la primera línea MAYÚSCULA válida
        for (x0, y0, x1, y1, text) in blocks:
            for ln in text.splitlines():
                ln = ln.strip()
                if ln and ln.isupper() and len(ln) > 3 and ln.upper() != "FACTURA":
                    nombre = limpiar_nombre_cliente_raw(ln)
                    if nombre:
                        return nombre

    except Exception as e:
        logging.warning(f"extraer_nombre_cliente fallo en {os.path.basename(pdf_path)}: {e}")

    return None


def extraer_numeros_albaran_ordenados(pdf_path):
    """
    Extrae los números de albarán en el orden en que aparecen en el texto de la factura.
    Patrón: Albarán Num. A25  487  de DD/MM/AAAA  -> extraemos '487' (y relleno a 4 dígitos).
    NO usar set() para no perder orden.
    """
    try:
        doc = fitz.open(pdf_path)
        texto = ""
        for page in doc:
            texto += page.get_text("text") + "\n"
        patron = re.compile(r"Albar[aá]n\s*(?:Num\.?)?\s*A\d{2}\s*(\d{1,4})", flags=re.IGNORECASE)
        encontrados = [m.group(1).zfill(4) for m in patron.finditer(texto)]
        return encontrados  # puede contener duplicados si aparecen repetidos
    except Exception as e:
        logging.warning(f"extraer_numeros_albaran_ordenados fallo en {os.path.basename(pdf_path)}: {e}")
        return []


# -------------------------
# BÚSQUEDA RECURSIVA Y UNIÓN
# -------------------------
def buscar_albaran_primero(num, carpeta_base):
    """
    Devuelve la primera ruta de PDF encontrada que contenga el número `num` en su nombre,
    buscando recursivamente. Si hay varias coincidencias, devuelve la que tenga el nombre más cercano
    (podríamos refinar la heurística más adelante).
    """
    for root, _, files in os.walk(carpeta_base):
        for f in files:
            if not f.lower().endswith(".pdf"):
                continue
            if re.search(rf"\b{re.escape(num)}\b", f):
                return os.path.join(root, f)
    return None


def combinar_pdfs(lista_paths, salida_path):
    writer = PdfWriter()
    for p in lista_paths:
        try:
            reader = PdfReader(p)
            for pg in reader.pages:
                writer.add_page(pg)
        except Exception as e:
            logging.error(f"Error leyendo {p}: {e}")
    try:
        with open(salida_path, "wb") as out_f:
            writer.write(out_f)
    except Exception as e:
        logging.error(f"Error escribiendo salida {salida_path}: {e}")
        raise


# -------------------------
# PROGRAMA PRINCIPAL
# -------------------------
def main():
    logging.info("=== INICIO DEL PROCESO ===")

    Tk().withdraw()
    messagebox.showinfo("Seleccionar carpetas",
                        "A continuación se le pedirá seleccionar TRES carpetas, en este orden:\n\n"
                        "1) Carpeta que contiene las FACTURAS a procesar.\n"
                        "2) Carpeta base donde buscar los ALBARANES (se buscará también en subcarpetas).\n"
                        "3) Carpeta DESTINO donde se escribirán las facturas completas.\n\n"
                        "Pulse Aceptar para continuar.")

    carpeta_facturas = filedialog.askdirectory(title="Carpeta: FACTURAS a procesar")
    carpeta_albaranes = filedialog.askdirectory(title="Carpeta base de ALBARANES (se busca recursivamente)")
    carpeta_destino = filedialog.askdirectory(title="Carpeta DESTINO para facturas completas")

    if not all([carpeta_facturas, carpeta_albaranes, carpeta_destino]):
        logging.error("Proceso cancelado: no se seleccionaron todas las carpetas.")
        messagebox.showwarning("Proceso cancelado", "No se seleccionaron las 3 carpetas requeridas. Saliendo.")
        return

    logging.info(f"Carpeta facturas: {carpeta_facturas}")
    logging.info(f"Carpeta albaranes: {carpeta_albaranes}")
    logging.info(f"Carpeta destino: {carpeta_destino}")

    archivos_facturas = [f for f in os.listdir(carpeta_facturas) if f.lower().endswith(".pdf")]
    logging.info(f"Facturas detectadas: {len(archivos_facturas)}")

    total_procesadas = 0
    albaranes_faltantes = []  # lista de tuples (factura, numero)

    # Procesamos en orden de lista; registramos cada paso en log (para ver 'progreso')
    for factura in archivos_facturas:
        try:
            ruta_factura = os.path.join(carpeta_facturas, factura)
            logging.info(f"--> Procesando factura: {factura}")

            # Extraer nombre cliente (bloque superior derecho preferente)
            nombre_cliente = extraer_nombre_cliente(ruta_factura)
            logging.info(f"    Nombre cliente detectado: {nombre_cliente}")

            # Extraer numeros de albaran en orden
            nums = extraer_numeros_albaran_ordenados(ruta_factura)
            logging.info(f"    Albaranes detectados (orden): {nums}")

            if not nums:
                logging.warning(f"    No se detectaron albaranes en {factura}")
                continue

            # Construir lista de archivos a unir (factura + albaranes en el mismo orden)
            lista_a_unir = [ruta_factura]
            encontrados_para_factura = 0
            for num in nums:
                ruta_alb = buscar_albaran_primero(num, carpeta_albaranes)
                if ruta_alb:
                    lista_a_unir.append(ruta_alb)
                    encontrados_para_factura += 1
                    logging.info(f"        Albarán {num} encontrado: {ruta_alb}")
                else:
                    logging.warning(f"        Albarán {num} NO encontrado para {factura}")
                    albaranes_faltantes.append((factura, num))

            if encontrados_para_factura == 0:
                logging.info(f"    Ningún albarán encontrado para {factura}, se salta creación de combinado.")
                continue

            # nombre de salida: agregar nombre cliente si existe (limpio)
            base, ext = os.path.splitext(factura)
            if nombre_cliente:
                salida_nombre = f"{base} {nombre_cliente}{ext}"
            else:
                salida_nombre = f"{base}{ext}"

            salida_path = os.path.join(carpeta_destino, salida_nombre)

            # Si existe salida con mismo nombre, evitar sobreescribir: añadir contador
            contador = 1
            final_path = salida_path
            while os.path.exists(final_path):
                final_path = os.path.join(carpeta_destino, f"{os.path.splitext(salida_nombre)[0]} ({contador}){ext}")
                contador += 1

            combinar_pdfs(lista_a_unir, final_path)
            total_procesadas += 1
            logging.info(f"    Creado combinado: {final_path} (albaranes añadidos: {encontrados_para_factura})")

        except Exception as e:
            logging.exception(f"Error procesando factura {factura}: {e}")
            # seguimos con la siguiente factura

    # Resumen final
    logging.info("=== RESUMEN FINAL ===")
    logging.info(f"Facturas procesadas (combinadas): {total_procesadas} de {len(archivos_facturas)}")
    if albaranes_faltantes:
        logging.info("Albaranes no encontrados (lista):")
        for fct, num in albaranes_faltantes:
            logging.info(f"  {fct} -> {num}")
        logging.info(f"Total albaranes faltantes: {len(albaranes_faltantes)}")
    else:
        logging.info("No faltaron albaranes. Todos localizados.")

    # Mostrar mensaje final y abrir log para inspección
    try:
        messagebox.showinfo("Proceso completado",
                            f"Proceso completado.\nFacturas combinadas: {total_procesadas} de {len(archivos_facturas)}.\n"
                            f"Se ha generado el log en:\n{LOG_FILE}\n\nSe abrirá el log para su revisión.")
        # Abrir el log con la aplicación por defecto (Notepad en Windows)
        try:
            if sys.platform.startswith("win"):
                os.startfile(LOG_FILE)
            else:
                # mac / linux
                import subprocess
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", LOG_FILE])
        except Exception:
            logging.warning("No se pudo abrir automáticamente el fichero de log.")
    except Exception:
        # si messagebox falla (raro), solo logueamos
        logging.info("Proceso finalizado. Revisar log.")

# -------------------------
if __name__ == "__main__":
    main()
