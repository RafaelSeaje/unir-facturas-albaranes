#!/usr/bin/env python3
"""
procesa_facturas_y_albaranes.py
Versión robusta (sin consola), OCR automático para facturas si hace falta,
búsqueda de albaranes por nombre y por contenido (opcional), progress UI y log.
"""

import os
import re
import io
import logging
import traceback
import fitz                        # PyMuPDF
import pytesseract
from PIL import Image
import PyPDF2
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ----------------- CONFIGURACIÓN -----------------
# Si tu instalación de Tesseract no está en PATH, ponla aquí:
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"  # <--- ajusta si hace falta
# Si no quieres que el script busque dentro del contenido de los albaranes (más lento),
# pon False. Si lo pones True, hará lectura y OCR de albaranes si no se encuentra por nombre.
SEARCH_ALBARAN_BY_CONTENT_IF_NOT_FOUND = True

# Log (sobrescribe cada ejecución)
LOG_FILENAME = "procesa_facturas_log.txt"
logging.basicConfig(
    filename=LOG_FILENAME,
    filemode="w",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Configuración pytesseract
try:
    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
except Exception as e:
    logging.warning(f"No se pudo configurar Tesseract: {e}")

# Regex patrón basado en tu ejemplo "Albarán Num. A25  487  de 07/04/2025"
RE_ALBARAN_PATTERN = re.compile(
    r"[Aa]lbar[aá]n\s*(?:N[úu]m\.?|N[ºo]\.?)?\s*A?\d{0,3}\s*(\d{1,5})",
    flags=re.IGNORECASE
)

# ----------------- UTILS -----------------
def seleccionar_carpeta(titulo):
    root = tk.Tk()
    root.withdraw()
    carpeta = filedialog.askdirectory(title=titulo)
    root.destroy()
    if not carpeta:
        raise SystemExit("No se seleccionó carpeta.")
    logging.info(f"Carpeta seleccionada: {carpeta}")
    return carpeta

def safe_make_dir(path):
    os.makedirs(path, exist_ok=True)

def extract_text_pymupdf(pdf_path):
    """Extrae texto de todo el PDF con PyMuPDF; devuelve '' si no hay texto."""
    try:
        doc = fitz.open(pdf_path)
        all_text = []
        for page in doc:
            t = page.get_text("text") or ""
            all_text.append(t)
        doc.close()
        return "\n".join(all_text).strip()
    except Exception as e:
        logging.error(f"PyMuPDF error leyendo {pdf_path}: {e}")
        return ""

def ocr_pdf_to_text(pdf_path, dpi=200, lang='spa'):
    """Aplica OCR (pytesseract) a cada página del PDF y devuelve el texto."""
    text_parts = []
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            txt = pytesseract.image_to_string(img, lang=lang)
            text_parts.append(txt)
        doc.close()
    except Exception as e:
        logging.error(f"OCR fallo en {pdf_path}: {e}")
    return "\n".join(text_parts).strip()

def extract_text_with_ocr_fallback(pdf_path):
    """Intenta PyMuPDF, y si no hay texto, aplica OCR (para facturas)."""
    text = extract_text_pymupdf(pdf_path)
    if text and text.strip():
        return text
    # fallback to OCR
    logging.info(f"No se encontró texto nativo en {os.path.basename(pdf_path)} -> aplicando OCR")
    return ocr_pdf_to_text(pdf_path)

def extract_albaran_numbers_from_text(text):
    """Extrae todos los números de albarán del texto según el patrón definido."""
    nums = RE_ALBARAN_PATTERN.findall(text or "")
    # normalizar y eliminar duplicados, devolver como strings sin ceros rellenos
    nums_norm = []
    for n in nums:
        nstr = n.strip()
        if nstr:
            nums_norm.append(nstr.lstrip("0"))  # guardar sin ceros a izquierda para coincidencia flexible
    return list(dict.fromkeys(nums_norm))  # mantener orden y eliminar duplicados

def find_albaran_by_number_in_folder(folder, num):
    """Busca un PDF en folder cuyo nombre contenga num (con o sin ceros delante)."""
    # chequea varias variantes: exacto, con ceros a 4 dígitos, con Axx prefijo
    candidates = []
    num_int = None
    try:
        num_int = int(re.sub(r'\D', '', num))
    except Exception:
        num_int = None

    padded4 = f"{int(num):04d}" if num.isdigit() else None

    for fname in os.listdir(folder):
        if not fname.lower().endswith(".pdf"):
            continue
        name = fname.lower()
        # quick checks
        if num.lower() in name:
            candidates.append((1, fname))
            continue
        if padded4 and padded4 in name:
            candidates.append((2, fname))
            continue
        # try to strip non-digits and compare
        digits_in_name = "".join(re.findall(r"\d+", fname))
        if digits_in_name and num_int is not None and str(num_int) in digits_in_name:
            candidates.append((3, fname))
    # ordenar por prioridad (menor mejor)
    candidates.sort(key=lambda x: x[0])
    return [os.path.join(folder, c[1]) for c in candidates]

def find_albaran_by_content(folder, num):
    """Busca dentro del contenido de PDFs de folder el número num (usa texto nativo y OCR si hace falta)."""
    matches = []
    for fname in os.listdir(folder):
        if not fname.lower().endswith(".pdf"):
            continue
        path = os.path.join(folder, fname)
        text = extract_text_pymupdf(path)
        if text and re.search(rf"\b{re.escape(num)}\b", text):
            matches.append(path)
            continue
        # fallback to OCR only if configured
        if SEARCH_ALBARAN_BY_CONTENT_IF_NOT_FOUND:
            ocrt = ocr_pdf_to_text(path)
            if ocrt and re.search(rf"\b{re.escape(num)}\b", ocrt):
                matches.append(path)
    return matches

def merge_pdfs(output_path, list_of_paths):
    """Une PDFs en output_path; devuelve True si se escribió algo."""
    try:
        merger = PyPDF2.PdfMerger()
        for p in list_of_paths:
            merger.append(p)
        merger.write(output_path)
        merger.close()
        return True
    except Exception as e:
        logging.error(f"Error al unir PDFs en {output_path}: {e}")
        return False

# ----------------- UI de progreso (simple, no consola) -----------------
class ProgressWindow:
    def __init__(self, total, title="Procesando"):
        self.root = tk.Tk()
        self.root.title(title)
        self.root.resizable(False, False)
        self.total = max(1, total)
        self.var = tk.DoubleVar(value=0)
        self.label = tk.Label(self.root, text=f"0 / {self.total}")
        self.label.pack(padx=10, pady=(10,0))
        self.pb = ttk.Progressbar(self.root, orient="horizontal", length=400, mode="determinate", maximum=self.total, variable=self.var)
        self.pb.pack(padx=10, pady=(5,10))
        # center window
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"+{x}+{y}")
        # don't block mainloop yet; we'll update manually
    def update(self, value, message=None):
        self.var.set(value)
        self.label.config(text=f"{int(value)} / {self.total}" + (f" — {message}" if message else ""))
        self.root.update_idletasks()
    def close(self):
        try:
            self.root.destroy()
        except Exception:
            pass

# ----------------- PROCESO PRINCIPAL -----------------
def main():
    logging.info("=== INICIO DEL PROCESO ===")
    try:
        carpeta_facturas = seleccionar_carpeta("Seleccione la carpeta con las FACTURAS a procesar")
        carpeta_albaranes = seleccionar_carpeta("Seleccione la carpeta con los ALBARANES (renombrados)")
        carpeta_destino = seleccionar_carpeta("Seleccione la carpeta DESTINO para las facturas completas")
        safe_make_dir(carpeta_destino)

        facturas = [f for f in os.listdir(carpeta_facturas) if f.lower().endswith(".pdf")]
        logging.info(f"Facturas detectadas: {len(facturas)}")

        if not facturas:
            messagebox.showinfo("Sin facturas", "No se encontrarón archivos PDF en la carpeta de facturas.")
            logging.info("No hay facturas para procesar. Saliendo.")
            return

        prog = ProgressWindow(total=len(facturas), title="Procesando facturas y albaranes")
        processed = 0
        i = 0

        for factura in facturas:
            i += 1
            try:
                prog.update(i-1, f"Analizando {factura}")
                ruta_factura = os.path.join(carpeta_facturas, factura)

                # Extraer texto: preferimos texto nativo; si no, OCR
                text = extract_text_pymupdf(ruta_factura)
                used_ocr = False
                if not text.strip():
                    text = ocr_pdf_to_text(ruta_factura)
                    used_ocr = True
                    logging.info(f"OCR aplicado a factura {factura}")

                nums = extract_albaran_numbers_from_text(text)
                logging.info(f"Factura {factura}: números de albarán detectados: {nums} (OCR usado: {used_ocr})")

                if not nums:
                    logging.info(f"No se detectaron números de albarán en {factura}")
                    prog.update(i, f"Sin albaranes: {factura}")
                    continue

                # localizar archivos de albaranes
                albaranes_paths = []
                for num in nums:
                    found_by_name = find_albaran_by_number_in_folder(carpeta_albaranes, num)
                    if found_by_name:
                        albaranes_paths.extend(found_by_name)
                        logging.info(f"Albarán(s) por nombre para {num}: {[os.path.basename(p) for p in found_by_name]}")
                        continue
                    # si no encontrado por nombre, buscar por contenido (opcional)
                    if SEARCH_ALBARAN_BY_CONTENT_IF_NOT_FOUND:
                        found_by_content = find_albaran_by_content(carpeta_albaranes, num)
                        if found_by_content:
                            albaranes_paths.extend(found_by_content)
                            logging.info(f"Albarán(s) por contenido para {num}: {[os.path.basename(p) for p in found_by_content]}")
                        else:
                            logging.warning(f"No se encontró albarán {num} en carpeta {carpeta_albaranes}")

                # quitar duplicados y mantener orden
                seen = set()
                albaranes_paths_unique = []
                for p in albaranes_paths:
                    if p not in seen:
                        seen.add(p)
                        albaranes_paths_unique.append(p)

                if not albaranes_paths_unique:
                    logging.warning(f"No se encontraron albaranes para factura {factura}")
                    prog.update(i, f"Albaranes no encontrados: {factura}")
                    continue

                # Unir factura + albaranes
                salida = os.path.join(carpeta_destino, factura)
                sources = [ruta_factura] + albaranes_paths_unique
                ok = merge_ok = merge_pdfs(salida, sources)
                if ok:
                    processed += 1
                    logging.info(f"Factura completa generada: {os.path.basename(salida)} con {len(albaranes_paths_unique)} albaranes")
                    prog.update(i, f"Generado: {os.path.basename(salida)}")
                else:
                    logging.error(f"Fallo al generar {os.path.basename(salida)}")
                    prog.update(i, f"Error generando: {factura}")

            except Exception as e:
                logging.error(f"Error procesando factura {factura}: {traceback.format_exc()}")
                prog.update(i, f"Error: {factura}")
            # small UI refresh
        prog.close()

        logging.info(f"=== FIN DEL PROCESO. Facturas procesadas: {processed} de {len(facturas)} ===")
        messagebox.showinfo("Proceso finalizado", f"Facturas procesadas: {processed} de {len(facturas)}\nRevisa {LOG_FILENAME} para detalles.")

    except SystemExit as se:
        logging.info(f"Proceso cancelado por usuario: {se}")
    except Exception as e:
        logging.error("Error crítico: " + traceback.format_exc())
        try:
            messagebox.showerror("Error", f"Ocurrió un error: {e}\nVer log {LOG_FILENAME}")
        except Exception:
            pass

if __name__ == "__main__":
    main()
