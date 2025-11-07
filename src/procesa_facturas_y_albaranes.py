import os
import re
import sys
import fitz  # PyMuPDF
import logging
from PyPDF2 import PdfReader, PdfWriter
from tkinter import Tk, filedialog
from tqdm import tqdm

# ---------------------------------------------------------
# CONFIGURACIÓN DE LOGGING
# ---------------------------------------------------------
LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "procesa_facturas_log.txt")
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="w"
)

# ---------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------
def limpiar_nombre_cliente(nombre):
    """Normaliza el nombre del cliente eliminando abreviaturas y caracteres no válidos."""
    nombre = nombre.strip().replace('.', '')
    nombre = re.sub(r'\b(SL|SA|SLU|SLL|SCOOP|SCOOPG|SC)\b', '', nombre, flags=re.IGNORECASE)
    nombre = re.sub(r'\s{2,}', ' ', nombre).strip()
    nombre = re.sub(r'[\/\\\:\*\?\"\<\>\|]', '_', nombre)
    return nombre

def extraer_nombre_cliente(pdf_path):
    """Extrae el nombre del cliente de la parte superior derecha del PDF."""
    try:
        doc = fitz.open(pdf_path)
        texto = ""
        for page in doc:
            texto += page.get_text("text")
            break  # solo primera página
        if not texto:
            return None
        for linea in texto.splitlines():
            if linea.strip().isupper() and len(linea.strip()) > 3:
                return limpiar_nombre_cliente(linea)
        return None
    except Exception as e:
        logging.warning(f"No se pudo leer el cliente en {pdf_path}: {e}")
        return None

def extraer_numeros_albaran(pdf_path):
    """Extrae todos los números de albarán del texto del PDF."""
    try:
        texto = ""
        doc = fitz.open(pdf_path)
        for page in doc:
            texto += page.get_text("text") or ""
        patron = r"Albar[aá]n\s*Num\.?\s*A\d{2}\s*(\d{1,4})"
        encontrados = re.findall(patron, texto, flags=re.IGNORECASE)
        return list(set([x.zfill(4) for x in encontrados]))
    except Exception as e:
        logging.warning(f"No se pudo extraer albaranes en {pdf_path}: {e}")
        return []

def buscar_albaran(num, carpeta_base):
    """Busca un albarán en la carpeta base y subcarpetas."""
    resultados = []
    for root, _, files in os.walk(carpeta_base):
        for f in files:
            if f.lower().endswith(".pdf") and re.search(rf"\b{num}\b", f):
                resultados.append(os.path.join(root, f))
    return resultados

def combinar_pdfs(lista_paths, salida_path):
    """Combina varios PDFs en un único archivo."""
    writer = PdfWriter()
    for path in lista_paths:
        try:
            reader = PdfReader(path)
            for page in reader.pages:
                writer.add_page(page)
        except Exception as e:
            logging.error(f"No se pudo leer {path}: {e}")
    with open(salida_path, "wb") as f_out:
        writer.write(f_out)

# ---------------------------------------------------------
# PROCESO PRINCIPAL
# ---------------------------------------------------------
def main():
    logging.info("=== INICIO DEL PROCESO ===")

    # Selección de carpetas
    Tk().withdraw()
    carpeta_facturas = filedialog.askdirectory(title="Selecciona la carpeta de facturas")
    carpeta_albaranes = filedialog.askdirectory(title="Selecciona la carpeta base de albaranes")
    carpeta_destino = filedialog.askdirectory(title="Selecciona la carpeta de destino para las facturas completas")

    if not all([carpeta_facturas, carpeta_albaranes, carpeta_destino]):
        logging.error("Proceso cancelado: no se seleccionaron todas las carpetas.")
        return

    logging.info(f"Carpeta de facturas: {carpeta_facturas}")
    logging.info(f"Carpeta de albaranes: {carpeta_albaranes}")
    logging.info(f"Carpeta destino: {carpeta_destino}")

    facturas = [f for f in os.listdir(carpeta_facturas) if f.lower().endswith(".pdf")]
    logging.info(f"Facturas detectadas: {len(facturas)}")

    no_encontrados = []

    # Verificar si estamos en un entorno con consola o sin ella
    use_tqdm = sys.stdout.isatty() if sys.stdout else False

    for factura in tqdm(facturas, desc="Procesando facturas", unit="factura", disable=not use_tqdm):
        ruta_factura = os.path.join(carpeta_facturas, factura)
        nombre_cliente = extraer_nombre_cliente(ruta_factura)
        numeros_albaran = extraer_numeros_albaran(ruta_factura)
        logging.info(f"Factura {factura}: albaranes detectados {numeros_albaran}")

        if not numeros_albaran:
            logging.warning(f"No se detectaron albaranes en {factura}")
            continue

        archivos_a_unir = [ruta_factura]
        for num in numeros_albaran:
            encontrados = buscar_albaran(num, carpeta_albaranes)
            if encontrados:
                for a in encontrados:
                    archivos_a_unir.append(a)
                    logging.info(f"✓ Albarán {num} vinculado a {factura}: {a}")
            else:
                logging.warning(f"No se encontró albarán {num} para {factura}")
                no_encontrados.append(f"{factura} → {num}")

        if len(archivos_a_unir) == 1:
            continue

        base, ext = os.path.splitext(factura)
        if nombre_cliente:
            nuevo_nombre = f"{base} {nombre_cliente}{ext}"
        else:
            nuevo_nombre = f"{base}{ext}"

        salida_path = os.path.join(carpeta_destino, nuevo_nombre)
        combinar_pdfs(archivos_a_unir, salida_path)
        logging.info(f"Factura completa generada: {nuevo_nombre} ({len(archivos_a_unir)-1} albaranes)")

    if no_encontrados:
        logging.info("=== ALBARANES NO ENCONTRADOS ===")
        for item in no_encontrados:
            logging.info(item)
        logging.info(f"Total no encontrados: {len(no_encontrados)}")
    else:
        logging.info("Todos los albaranes fueron encontrados y procesados correctamente.")

    logging.info(f"=== FIN DEL PROCESO. Facturas procesadas: {len(facturas)} ===")
    print("\n✅ Proceso completado. Revisa el log para más detalles.")

# ---------------------------------------------------------
if __name__ == "__main__":
    main()
