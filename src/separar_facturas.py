#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
separar_facturas.py
Módulo para separar un PDF que contiene muchas facturas en PDFs individuales,
agrupando páginas que pertenecen a la misma factura.

Versión corregida:
 - Normaliza la "clave" de factura para evitar que pequeñas variaciones OCR
   provoquen que páginas de la misma factura se separen.
 - Mantiene la lógica original de OCR/recorte pero estabiliza la comparación.
"""

import os
import re
import threading
import datetime
import logging
from io import BytesIO

import fitz                     # PyMuPDF
from PIL import Image
import pytesseract
from pypdf import PdfReader, PdfWriter
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# -------------------- CONFIGURACIÓN --------------------
# Ruta a tesseract (ajusta si en tu equipo es diferente - ya la tenemos).
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Rectángulo del número/fecha de factura en mm sobre A4:
RECT_MM = {"left_mm": 7.0, "width_mm": 68.0, "top_mm": 57.0, "height_mm": 17.0}

# DPI / zoom para renderizado: mayor zoom → mejor OCR, pero más tiempo/uso memoria
RENDER_ZOOM = 2.0

# Carpeta de logs (se sobrescribe a cada ejecución)
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "separar_facturas.log")

# Regex para detectar número/serie y fecha
RE_SERIE_NUM = re.compile(r'^\s*([A-Za-z]{1,5})?\s*([0-9]{1,4})\b', re.IGNORECASE)
RE_FECHA = re.compile(r'([0-3]?\d/[01]?\d/[12]\d{3})')

# Mapa de corrección de confusiones OCR típicas (aplicado solo en la porción numérica)
OCR_CONFUSION_MAP = str.maketrans({
    'O': '0', 'o': '0',
    'I': '1', 'l': '1', '|': '1',
    'Z': '2',
    'S': '5',
    'B': '8',
    '—': '-', '–': '-'
})

# -------------------- LOGGER --------------------
def configurar_logger():
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        filename=LOG_FILE,
        filemode='w',  # sobreescribir cada ejecución
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    # también emitir a consola útil cuando se ejecuta en python directamente
    if not any(isinstance(h, logging.StreamHandler) for h in logging.getLogger().handlers):
        logging.getLogger().addHandler(logging.StreamHandler())
    logging.info("=== INICIO: separar_facturas ===")
    logging.info(f"RECT_MM: {RECT_MM}, RENDER_ZOOM: {RENDER_ZOOM}")

# -------------------- UTILIDADES OCR / IMAGEN --------------------
def render_page_to_image(page, zoom=RENDER_ZOOM):
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return img

def crop_region_from_image(img, page_width_pts, page_height_pts):
    pts_per_mm = 72.0 / 25.4
    left_pt = RECT_MM["left_mm"] * pts_per_mm
    top_pt = RECT_MM["top_mm"] * pts_per_mm
    right_pt = (RECT_MM["left_mm"] + RECT_MM["width_mm"]) * pts_per_mm
    bottom_pt = (RECT_MM["top_mm"] + RECT_MM["height_mm"]) * pts_per_mm

    # expandimos ligeramente el recorte para evitar cortes (margen de seguridad)
    MARGIN_H_PCT = 0.10  # 10% horizontal
    MARGIN_V_PCT = 0.15  # 15% vertical

    width_pt = right_pt - left_pt
    height_pt = bottom_pt - top_pt

    left_pt = max(0, left_pt - width_pt * MARGIN_H_PCT)
    right_pt = right_pt + width_pt * MARGIN_H_PCT
    top_pt = max(0, top_pt - height_pt * MARGIN_V_PCT)
    bottom_pt = bottom_pt + height_pt * MARGIN_V_PCT

    scale = RENDER_ZOOM
    left_px = int(round(left_pt * scale))
    top_px = int(round(top_pt * scale))
    right_px = int(round(right_pt * scale))
    bottom_px = int(round(bottom_pt * scale))

    left_px = max(0, left_px)
    top_px = max(0, top_px)
    right_px = min(img.width, right_px)
    bottom_px = min(img.height, bottom_px)

    if right_px <= left_px or bottom_px <= top_px:
        return None

    return img.crop((left_px, top_px, right_px, bottom_px))

def ocr_image_to_text(img):
    try:
        gray = img.convert("L")
        text = pytesseract.image_to_string(gray, lang='spa', config="--psm 6")
        text = text.replace('\r', '\n').strip()
        return text
    except Exception as e:
        logging.error(f"OCR falló: {e}")
        return ""

# -------------------- EXTRACCIÓN Y NORMALIZACIÓN --------------------
def normalize_numeric_part(s):
    """
    Normaliza una cadena intentando corregir confusiones OCR típicas
    y extraer la porción numérica inicial.
    Devuelve la porción numérica como string (sin ceros a la izquierda) o None.
    """
    if not s:
        return None
    # aplicar map de confusiones (solo para facilitar detección)
    s_mapped = s.translate(OCR_CONFUSION_MAP)
    # buscar primero 'serie + número' patrón
    m = RE_SERIE_NUM.match(s_mapped)
    if m:
        serie = (m.group(1) or "").strip().upper()
        num = m.group(2)
        # devolver num sin ceros a la izquierda (pero manteniendo "0" si es "0")
        return serie if serie else "", num.lstrip('0') or num
    # si no hay serie+num al inicio, buscar primer grupo de 1-4 dígitos
    m2 = re.search(r'([0-9]{1,4})', s_mapped)
    if m2:
        return "", m2.group(1).lstrip('0') or m2.group(1)
    return None

def extract_number_and_date_from_text(block_text):
    """
    Extrae raw_number, fecha_iso, serie, num_str a partir del texto del bloque.
    """
    if not block_text:
        return None, None, None, None

    lines = [l.strip() for l in block_text.splitlines() if l.strip()]
    raw_number = None
    fecha_iso = None

    # buscar línea con 'Factura'
    idx = None
    for i, line in enumerate(lines):
        if re.search(r'\bFactura\b', line, flags=re.IGNORECASE):
            idx = i
            break

    candidate = None
    if idx is not None:
        line = lines[idx]
        if ':' in line and re.search(r':\s*\S+', line):
            after = line.split(':', 1)[1].strip()
            if after:
                candidate = after
        if not candidate and idx + 1 < len(lines):
            candidate = lines[idx + 1]

    if not candidate:
        for line in lines:
            m = re.search(r'Factura[:\s]*', line, flags=re.IGNORECASE)
            if m:
                after = line[m.end():].strip()
                if after:
                    candidate = after
                    break
        if not candidate:
            candidate = lines[0] if lines else None

    if candidate:
        raw_number = candidate.strip()

    # extraer fecha si aparece
    for line in lines:
        m = RE_FECHA.search(line)
        if m:
            try:
                d = datetime.datetime.strptime(m.group(1), "%d/%m/%Y")
                fecha_iso = d.strftime("%Y-%m-%d")
            except Exception:
                fecha_iso = None
            break

    # intentar extraer serie+numero con normalización robusta
    serie = None
    num_str = None
    if raw_number:
        norm = normalize_numeric_part(raw_number)
        if norm:
            # norm puede devolver ("SERIE", "123") o ("", "123")
            if isinstance(norm, tuple):
                serie_part, num_part = norm
                serie = serie_part if serie_part else None
                num_str = num_part
            else:
                # si por alguna razón devuelve un solo valor, lo tomamos como num_str
                num_str = str(norm)

    return raw_number, fecha_iso, serie, num_str

# -------------------- GUARDADO --------------------
def save_invoice_pdf_from_reader(reader, page_indexes, outdir, fecha_iso, serie, num_str, raw_number):
    os.makedirs(outdir, exist_ok=True)

    if num_str:
        num_pad = str(num_str).zfill(4)
        fecha_txt = fecha_iso if fecha_iso else "0000-00-00"
        serie_txt = f" {serie}" if serie else ""
        filename = f"{fecha_txt} FE#{num_pad}{serie_txt}.pdf"
    else:
        safe_raw = re.sub(r'[\/\\\:\*\?\"\<\>\|]', '_', (raw_number or "SIN_NUMERO")).strip()
        fecha_txt = fecha_iso if fecha_iso else "0000-00-00"
        filename = f"{fecha_txt} {safe_raw}.pdf"

    outpath = os.path.join(outdir, filename)
    base, ext = os.path.splitext(outpath)
    counter = 1
    while os.path.exists(outpath):
        outpath = f"{base} ({counter}){ext}"
        counter += 1

    writer = PdfWriter()
    for p in page_indexes:
        writer.add_page(reader.pages[p])
    with open(outpath, 'wb') as f:
        writer.write(f)

    logging.info(f"Guardado: {outpath}")
    return outpath

# -------------------- PROCESAMIENTO PRINCIPAL --------------------
def make_key_from_parts(serie, num_str, raw_number):
    """
    Genera una clave canónica para comparar facturas entre páginas.
    Prioriza serie+num_str si existe; si no, intenta normalizar raw_number.
    """
    if num_str:
        s = (serie or "").upper()
        return f"{s}#{str(num_str).zfill(4)}"
    if raw_number:
        # extraer mediante normalize_numeric_part (aplicar same mapping)
        norm = normalize_numeric_part(raw_number)
        if norm and isinstance(norm, tuple):
            s_part, n_part = norm
            s_part = s_part.upper() if s_part else ""
            return f"{s_part}#{str(n_part).zfill(4)}"
        # fallback: usar RAW con texto limpio compactado
        raw_clean = re.sub(r'\s+', ' ', raw_number).strip()
        return f"RAW#{raw_clean}"
    return None

def procesar_pdf_separar(input_pdf_path, output_dir, progress_callback=None, status_callback=None):
    try:
        reader = PdfReader(input_pdf_path)
    except Exception as e:
        logging.exception("No se pudo abrir PDF")
        if status_callback:
            status_callback(f"ERROR abriendo PDF: {e}")
        return 0, []

    doc = fitz.open(input_pdf_path)  # para render / imagen
    total_pages = len(doc)
    results_saved = []
    processed_invoices = 0

    current_number_key = None
    current_pages = []
    current_fecha = None
    current_serie = None
    current_num_str = None
    current_raw = None

    for i in range(total_pages):
        if progress_callback:
            progress_callback(i + 1, total_pages)
        if status_callback:
            status_callback(f"Procesando página {i+1}/{total_pages}")

        page = doc[i]
        pil_img = render_page_to_image(page, zoom=RENDER_ZOOM)
        cropped = crop_region_from_image(pil_img, page.rect.width, page.rect.height)
        if cropped is None:
            logging.warning(f"P{i+1}: recorte inválido.")
            text_block = ""
        else:
            text_block = ocr_image_to_text(cropped)

        raw_number, fecha_iso, serie, num_str = extract_number_and_date_from_text(text_block)
        logging.info(f"P{i+1}: raw='{raw_number}' fecha='{fecha_iso}' serie='{serie}' num='{num_str}'")

        key = make_key_from_parts(serie, num_str, raw_number)
        logging.debug(f"P{i+1}: key generated -> {key}")

        if key is None:
            logging.warning(f"No se detectó número en página {i+1}. Texto OCR: '{(text_block or '')[:160]}'")
            if current_number_key is None:
                continue
            else:
                current_pages.append(i)
                continue

        # Si no hay factura en curso -> iniciar
        if current_number_key is None:
            current_number_key = key
            current_pages = [i]
            current_fecha = fecha_iso
            current_serie = serie
            current_num_str = num_str
            current_raw = raw_number
            logging.debug(f"P{i+1}: inicia factura {current_number_key}")
            continue

        # Si la clave ha cambiado -> guardar la anterior y comenzar nueva
        if key != current_number_key:
            saved_path = save_invoice_pdf_from_reader(reader, current_pages, output_dir,
                                                     current_fecha, current_serie, current_num_str, current_raw)
            results_saved.append(saved_path)
            processed_invoices += 1
            logging.debug(f"P{i+1}: cerrada factura {current_number_key} -> guardada {saved_path}")
            # iniciar nueva factura
            current_number_key = key
            current_pages = [i]
            current_fecha = fecha_iso
            current_serie = serie
            current_num_str = num_str
            current_raw = raw_number
        else:
            # misma factura -> añadir página
            current_pages.append(i)
            logging.debug(f"P{i+1}: añadida a factura {current_number_key}")

    # guardar la última factura en curso
    if current_pages and current_number_key is not None:
        saved_path = save_invoice_pdf_from_reader(reader, current_pages, output_dir,
                                                 current_fecha, current_serie, current_num_str, current_raw)
        results_saved.append(saved_path)
        processed_invoices += 1

    doc.close()
    logging.info(f"Proceso terminado. Facturas generadas: {processed_invoices}")
    if status_callback:
        status_callback(f"Proceso terminado. Facturas generadas: {processed_invoices}")
    return processed_invoices, results_saved

# -------------------- INTERFAZ GRÁFICA (Tk) --------------------
class AppSeparador:
    def __init__(self, root):
        self.root = root
        root.title("Separador de Facturas")
        root.geometry("700x360")
        root.resizable(False, False)

        frame = tk.Frame(root, padx=12, pady=10)
        frame.pack(fill=tk.BOTH, expand=False)

        tk.Label(frame, text="PDF origen con múltiples facturas:", anchor="w").grid(row=0, column=0, sticky="w")
        self.entry_pdf = tk.Entry(frame, width=70)
        self.entry_pdf.grid(row=1, column=0, columnspan=2, pady=4, sticky="w")
        tk.Button(frame, text="Seleccionar PDF", command=self.select_pdf).grid(row=1, column=2, padx=6)

        tk.Label(frame, text="Carpeta destino para facturas separadas:", anchor="w").grid(row=2, column=0, sticky="w")
        self.entry_out = tk.Entry(frame, width=70)
        self.entry_out.grid(row=3, column=0, columnspan=2, pady=4, sticky="w")
        tk.Button(frame, text="Seleccionar carpeta", command=self.select_out).grid(row=3, column=2, padx=6)

        self.progress = ttk.Progressbar(root, orient='horizontal', mode='determinate', length=640)
        self.progress.pack(pady=8)
        self.status_var = tk.StringVar(value="Listo")
        self.status_label = tk.Label(root, textvariable=self.status_var, anchor="w")
        self.status_label.pack(fill=tk.X, padx=12)

        btn_frame = tk.Frame(root, pady=6)
        btn_frame.pack()
        self.btn_start = tk.Button(btn_frame, text="INICIAR SEPARACIÓN", bg="#4CAF50", fg="white",
                                   font=("Arial", 11, "bold"), command=self.start_process)
        self.btn_start.pack(side=tk.LEFT, padx=6)
        tk.Button(btn_frame, text="Salir", command=root.quit).pack(side=tk.LEFT, padx=6)

        configurar_logger()

    def select_pdf(self):
        p = filedialog.askopenfilename(title="Seleccionar PDF", filetypes=[("PDF files", "*.pdf")])
        if p:
            self.entry_pdf.delete(0, tk.END)
            self.entry_pdf.insert(0, p)

    def select_out(self):
        p = filedialog.askdirectory(title="Seleccionar carpeta destino")
        if p:
            self.entry_out.delete(0, tk.END)
            self.entry_out.insert(0, p)

    def progress_callback(self, current, total):
        try:
            self.progress['maximum'] = total
            self.progress['value'] = current
            self.status_var.set(f"Procesando página {current} de {total}")
            self.root.update_idletasks()
        except Exception:
            pass

    def status_callback(self, msg):
        self.status_var.set(msg)
        logging.info(msg)
        self.root.update_idletasks()

    def start_process(self):
        input_pdf = self.entry_pdf.get().strip()
        output_dir = self.entry_out.get().strip()
        if not input_pdf or not output_dir:
            messagebox.showwarning("Faltan datos", "Seleccione el PDF origen y la carpeta destino.")
            return

        self.btn_start.config(state=tk.DISABLED)
        self.status_callback("Iniciando proceso...")
        self.progress['value'] = 0
        self.root.update_idletasks()

        thread = threading.Thread(target=self._run_process, args=(input_pdf, output_dir), daemon=True)
        thread.start()

    def _run_process(self, input_pdf, output_dir):
        try:
            processed_count, saved_paths = procesar_pdf_separar(
                input_pdf, output_dir,
                progress_callback=self.progress_callback,
                status_callback=self.status_callback
            )
            msg = f"Proceso finalizado. Facturas generadas: {processed_count}"
            messagebox.showinfo("Finalizado", msg)
            self.status_callback(msg)
        except Exception as e:
            logging.exception("Error en proceso principal")
            messagebox.showerror("Error", f"Ha ocurrido un error durante el proceso:\n{e}")
            self.status_callback(f"ERROR: {e}")
        finally:
            self.btn_start.config(state=tk.NORMAL)

def main():
    root = tk.Tk()
    app = AppSeparador(root)
    root.mainloop()

if __name__ == "__main__":
    main()
