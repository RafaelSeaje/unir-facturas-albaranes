#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
separar_facturas.py
Módulo para dividir un PDF que contiene muchas facturas en PDFs individuales por factura.
Detecta número de factura y fecha en el rectángulo superior-izq (coordenadas en cm), 
extrae nombre de cliente desde bloques en la zona superior-derecha y renombra cada PDF
según el patrón: YYYY-MM-DD FE#NNNN NOMBRE_CLIENTE.pdf

Requisitos:
  pip install PyMuPDF Pillow pytesseract pypdf
  Tesseract instalado en: C:\Program Files\Tesseract-OCR\tesseract.exe
"""

import os
import re
import logging
import shutil
from datetime import datetime
from io import BytesIO

import fitz  # PyMuPDF
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
import pytesseract
from pypdf import PdfReader, PdfWriter

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# -------------------- CONFIGURACIÓN --------------------
# Ruta a tesseract (confirmada)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Rectángulo del número/fecha de factura (cm desde borde superior-izq)
RECT_FACT_LEFT_CM = 0.7
RECT_FACT_TOP_CM = 5.7
RECT_FACT_RIGHT_CM = 7.6
RECT_FACT_BOTTOM_CM = 7.5
PAD_CM = 0.15  # pequeño padding por seguridad

# DPI para renderizado
RENDER_DPI = 300

# Carpeta de logs
LOGS_DIR = "logs"
FAIL_IMG_DIR = os.path.join(LOGS_DIR, "fails_images")

# Regex para detectar número de factura y fecha
RE_FACTURA = re.compile(r'Factura[:\s]*([A-Za-z0-9\-/]+|\d{1,})', re.IGNORECASE)  # captura lo que sigue a "Factura:"
# Si las facturas numericas son solo dígitos, lo extraemos con:
RE_FACTURA_NUM = re.compile(r'(\d{1,})')
RE_FECHA = re.compile(r'Fecha[:\s]*([0-3]?\d/[01]?\d/[12]\d{3})', re.IGNORECASE)

# Sufijos societarios a eliminar del nombre del cliente
SUFFIXES_RE = re.compile(r'\b(SL|SA|SLU|SCOOP|SLL|SCOOPG|SC|S\.L\.|S\.A\.)\b\.?$', re.IGNORECASE)

# -------------------- UTILIDADES --------------------
def configurar_logger():
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(FAIL_IMG_DIR, exist_ok=True)
    logname = datetime.now().strftime("separar_facturas_%Y%m%d_%H%M%S.log")
    logpath = os.path.join(LOGS_DIR, logname)
    logging.basicConfig(filename=logpath,
                        level=logging.INFO,
                        format="%(asctime)s - %(levelname)s - %(message)s")
    logging.info("=== INICIO: separar_facturas ===")
    return logpath

def cm_to_points(cm):
    return cm * (72.0 / 2.54)

def limpiar_nombre_cliente(nombre: str) -> str:
    if not nombre:
        return "CLIENTE"
    s = nombre.strip()
    s = s.replace('.', '')
    s = re.sub(SUFFIXES_RE, '', s).strip()
    s = re.sub(r'\s{2,}', ' ', s)
    s = re.sub(r'[\/\\\:\*\?\"\<\>\|]', '_', s)
    return s.upper()

# Extrae texto del bloque de interés usando PyMuPDF blocks
def extraer_texto_rect(page, rect):
    """
    Devuelve el texto extraído dentro del rect (fitz.Rect)
    """
    try:
        blocks = page.get_text("blocks")  # lista de (x0,y0,x1,y1, "text", block_no)
    except Exception as e:
        logging.error(f"get_text('blocks') falló: {e}")
        return ""
    textos = []
    for b in blocks:
        x0, y0, x1, y1, btext, _ = b
        # comprobar intersección con rect
        if x1 >= rect.x0 and x0 <= rect.x1 and y1 >= rect.y0 and y0 <= rect.y1:
            textos.append(btext)
    return "\n".join(textos).strip()

def render_rect_image(page, rect, dpi=RENDER_DPI):
    """
    Renderiza la región rect (fitz.Rect) de la página a PIL.Image RGB.
    """
    try:
        mat = fitz.Matrix(dpi/72.0, dpi/72.0)
        pix = page.get_pixmap(matrix=mat, clip=rect, alpha=False)
        img = Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")
        return img
    except Exception as e:
        logging.error(f"render_rect_image falló: {e}")
        return None

def preprocess_for_ocr(img: Image.Image) -> Image.Image:
    """
    Preprocesado simple para OCR: escala, gris, contraste, unsharp
    """
    img = img.convert("RGB")
    w,h = img.size
    img = img.resize((int(w*2), int(h*2)), Image.BICUBIC)
    gray = ImageOps.grayscale(img)
    enh = ImageEnhance.Contrast(gray)
    gray = enh.enhance(1.3)
    gray = gray.filter(ImageFilter.MedianFilter(size=3))
    gray = gray.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))
    return gray

def ocr_image_to_text(img: Image.Image, config="--psm 6"):
    try:
        text = pytesseract.image_to_string(img, lang='spa', config=config)
        return text
    except Exception as e:
        logging.error(f"OCR falló: {e}")
        return ""

# -------------------- LÓGICA DE DETECCIÓN EN UNA PÁGINA --------------------
def detectar_en_pagina(page):
    """
    Detecta número de factura, fecha y cliente en una página (fitz page).
    Devuelve (numero_string_or_None, fecha_iso_or_None, cliente_or_None, debug_text)
    """
    # calcular rect en puntos
    left = cm_to_points(max(0.0, RECT_FACT_LEFT_CM - PAD_CM))
    top = cm_to_points(max(0.0, RECT_FACT_TOP_CM - PAD_CM))
    right = cm_to_points(RECT_FACT_RIGHT_CM + PAD_CM)
    bottom = cm_to_points(RECT_FACT_BOTTOM_CM + PAD_CM)
    rect = fitz.Rect(left, top, right, bottom)

    # 1) intentar extraer texto directo de ese rect (si el PDF tiene texto)
    texto_rect = extraer_texto_rect(page, rect)
    numero = None
    fecha_iso = None
    cliente = None

    # buscar número en texto_rect
    if texto_rect:
        logging.info(f"Texto directo en rect: {texto_rect[:200]}")
        m = RE_FACTURA.search(texto_rect)
        if m:
            cand = m.group(1).strip()
            dm = RE_FACTURA_NUM.search(cand)
            if dm:
                numero = dm.group(1)
        mf = RE_FECHA.search(texto_rect)
        if mf:
            fecha_raw = mf.group(1)
            try:
                d = datetime.strptime(fecha_raw, "%d/%m/%Y")
                fecha_iso = d.strftime("%Y-%m-%d")
            except Exception:
                fecha_iso = None

    # 2) si no hay texto directo o falta datos, aplicar OCR a la zona
    if not numero or not fecha_iso:
        img = render_rect_image(page, rect)
        if img:
            proc = preprocess_for_ocr(img)
            ocr_text = ocr_image_to_text(proc, config="--psm 6")
            logging.info(f"OCR zona: {ocr_text.strip()[:250]}")
            if not numero:
                m = RE_FACTURA.search(ocr_text)
                if m:
                    cand = m.group(1).strip()
                    dm = RE_FACTURA_NUM.search(cand)
                    if dm:
                        numero = dm.group(1)
            if not fecha_iso:
                mf = RE_FECHA.search(ocr_text)
                if mf:
                    fecha_raw = mf.group(1)
                    try:
                        d = datetime.strptime(fecha_raw, "%d/%m/%Y")
                        fecha_iso = d.strftime("%Y-%m-%d")
                    except Exception:
                        fecha_iso = None

    # 3) extraer cliente: buscamos bloques en la zona superior-derecha de la página
    try:
        page_w = page.rect.width
        page_h = page.rect.height
        # definir zona superior-derecha como: x > 50% ancho, y < 35% alto
        blocks = page.get_text("blocks")
        cand_blocks = []
        for b in blocks:
            x0,y0,x1,y1, btext, _ = b
            if x0 > page_w * 0.45 and y0 < page_h * 0.35:
                cand_blocks.append((y0, btext.strip()))
        # ordenar por y (de arriba abajo)
        cand_blocks.sort(key=lambda x: x[0])
        # buscar primer bloque con línea en mayúsculas superior a 2 caracteres
        for _, btext in cand_blocks:
            for line in btext.splitlines():
                line2 = line.strip()
                if line2 and line2.isupper() and len(line2) > 2:
                    cliente = limpiar_nombre_cliente(line2)
                    break
            if cliente:
                break
        # si no encontrado, intentar en todo el texto superior con OCR
        if not cliente:
            # tomar región superior completa y OCR
            sup_rect = fitz.Rect(cm_to_points(10.0), 0, page_w, cm_to_points(4.5))  # ejemplo ancho derecha
            try:
                sup_img = render_rect_image(page, sup_rect)
                if sup_img:
                    proc2 = preprocess_for_ocr(sup_img)
                    t2 = ocr_image_to_text(proc2, config="--psm 6")
                    for line in t2.splitlines():
                        if line.strip() and line.strip().isupper() and len(line.strip()) > 2:
                            cliente = limpiar_nombre_cliente(line.strip())
                            break
            except Exception:
                pass
    except Exception as e:
        logging.error(f"Error extrayendo cliente: {e}")

    return numero, fecha_iso, cliente, texto_rect

# -------------------- FUNCIONES DE AGRUPACIÓN Y ESCRITURA --------------------
def agrupar_y_escribir(input_pdf_path, output_dir):
    """
    Lee el PDF completo, detecta número por página, agrupa páginas consecutivas
    con el mismo número y escribe PDFs individuales renombrados.
    """
    logging.info(f"Procesando archivo: {input_pdf_path}")
    os.makedirs(output_dir, exist_ok=True)

    reader = PdfReader(input_pdf_path)
    num_pages = len(reader.pages)
    logging.info(f"Páginas encontradas: {num_pages}")

    # Datos por página
    paginas_info = []  # lista de dicts: {page_index, numero, fecha, cliente, debug_text}
    doc = fitz.open(input_pdf_path)

    for i in range(num_pages):
        page = doc.load_page(i)
        numero, fecha_iso, cliente, debug_text = detectar_en_pagina(page)
        paginas_info.append({
            "idx": i,
            "numero": numero,
            "fecha": fecha_iso,
            "cliente": cliente,
            "debug": debug_text
        })
        logging.info(f"Página {i+1}: num={numero} fecha={fecha_iso} cliente={cliente}")

    # Agrupar páginas: cuando aparece un número no-nulo se inicia un nuevo grupo.
    grupos = []
    current = None
    for info in paginas_info:
        if info["numero"]:
            # iniciar nuevo grupo
            if current:
                grupos.append(current)
            current = {
                "numero": info["numero"],
                "fecha": info["fecha"],
                "cliente": info["cliente"],
                "pages": [info["idx"]]
            }
        else:
            # sin número: si hay grupo en curso, añadir; si no, acumular en un grupo 'unknown'
            if current:
                current["pages"].append(info["idx"])
            else:
                # grupo anonimo hasta encontrar numero: crear con numero None
                current = {
                    "numero": None,
                    "fecha": None,
                    "cliente": None,
                    "pages": [info["idx"]]
                }
    if current:
        grupos.append(current)

    logging.info(f"Grupos detectados: {len(grupos)}")

    # Si el primer grupo no tiene número y el siguiente sí, asignar ese número al primer grupo (caso encabezamiento)
    if len(grupos) >= 2 and grupos[0]["numero"] is None and grupos[1]["numero"]:
        logging.info("Primer grupo sin número; asignando número del siguiente grupo (posible encabezamiento).")
        grupos[0]["numero"] = grupos[1]["numero"]
        grupos[0]["fecha"] = grupos[1]["fecha"]
        grupos[0]["cliente"] = grupos[1]["cliente"]

    escritos = 0
    fallidos = []

    for g in grupos:
        numero = g["numero"]
        fecha = g["fecha"]
        cliente = g["cliente"] or "CLIENTE"
        pages = g["pages"]

        if not numero:
            logging.warning(f"Grupo sin número (páginas {pages}); se guarda como 'SIN_NUMERO_{pages[0]+1}.pdf'")
            out_name = f"SIN_NUMERO_{pages[0]+1}.pdf"
            out_path = os.path.join(output_dir, out_name)
        else:
            # número sin ceros -> rellenar a 4 dígitos
            num_pad = str(numero).zfill(4)
            # si no hay fecha, intentar buscar la primera página del grupo para la fecha
            if not fecha:
                # buscar en las páginas del grupo por primera fecha detectada
                for pidx in pages:
                    if paginas_info[pidx]["fecha"]:
                        fecha = paginas_info[pidx]["fecha"]
                        break
            fecha_final = fecha if fecha else "0000-00-00"
            # cliente limpiar
            cliente_clean = limpiar_nombre_cliente(cliente)
            out_name = f"{fecha_final} FE#{num_pad} {cliente_clean}.pdf"
            out_path = os.path.join(output_dir, out_name)

        # crear PDF con páginas indicadas
        try:
            writer = PdfWriter()
            for pidx in pages:
                writer.add_page(reader.pages[pidx])
            with open(out_path, "wb") as fout:
                writer.write(fout)
            escritos += 1
            logging.info(f"Escrito: {out_name} (páginas {pages})")
        except Exception as e:
            logging.error(f"Error escribiendo {out_path}: {e}")
            fallidos.append((pages, str(e)))
            # guardar imagen de la primera página del grupo para diagnóstico
            try:
                imgsave = os.path.join(FAIL_IMG_DIR, f"grupo_{pages[0]+1}.png")
                page_img = doc.load_page(pages[0]).get_pixmap(matrix=fitz.Matrix(150/72,150/72))
                page_img.save(imgsave)
                logging.info(f"Guardada imagen de fallo: {imgsave}")
            except Exception as e2:
                logging.error(f"No se pudo guardar imagen de fallo: {e2}")

    logging.info(f"Escritos: {escritos} documentos. Fallidos: {len(fallidos)}")
    return escritos, fallidos

# -------------------- INTERFAZ SIMPLE (Tk) --------------------
class AppSeparador:
    def __init__(self, root):
        self.root = root
        root.title("Separar facturas")
        root.geometry("620x220")
        root.resizable(False, False)

        self.label = tk.Label(root, text="Separar PDF de facturas en archivos individuales", font=("Segoe UI", 11))
        self.label.pack(pady=8)

        frame = tk.Frame(root)
        frame.pack(pady=6)

        self.btn_input = tk.Button(frame, text="Seleccionar PDF origen", width=20, command=self.select_input)
        self.btn_input.pack(side=tk.LEFT, padx=6)
        self.lbl_input = tk.Label(frame, text="Ninguno")
        self.lbl_input.pack(side=tk.LEFT, padx=6)

        self.btn_dest = tk.Button(frame, text="Seleccionar carpeta destino", width=22, command=self.select_output)
        self.btn_dest.pack(side=tk.LEFT, padx=6)
        self.lbl_dest = tk.Label(frame, text="Ninguno")
        self.lbl_dest.pack(side=tk.LEFT, padx=6)

        self.progress = ttk.Progressbar(root, orient='horizontal', mode='indeterminate', length=560)
        self.progress.pack(pady=12)
        self.progress.stop()

        self.text = tk.Text(root, height=6, width=78)
        self.text.pack(padx=6, pady=4)
        self.text.insert(tk.END, "Seleccione el PDF origen y la carpeta destino y pulse Iniciar.\n")
        self.text.config(state=tk.DISABLED)

        frame2 = tk.Frame(root)
        frame2.pack(pady=4)
        self.btn_start = tk.Button(frame2, text="Iniciar", command=self.start, width=12)
        self.btn_start.pack(side=tk.LEFT, padx=6)
        self.btn_quit = tk.Button(frame2, text="Salir", command=root.quit, width=12)
        self.btn_quit.pack(side=tk.LEFT, padx=6)

        self.input_pdf = None
        self.output_dir = None

    def log(self, s):
        self.text.config(state=tk.NORMAL)
        self.text.insert(tk.END, s + "\n")
        self.text.see(tk.END)
        self.text.config(state=tk.DISABLED)
        self.root.update()

    def select_input(self):
        path = filedialog.askopenfilename(title="Seleccionar PDF de facturas", filetypes=[("PDF Files", "*.pdf")])
        if path:
            self.input_pdf = path
            self.lbl_input.config(text=os.path.basename(path))

    def select_output(self):
        path = filedialog.askdirectory(title="Seleccionar carpeta destino")
        if path:
            self.output_dir = path
            self.lbl_dest.config(text=path)

    def start(self):
        if not self.input_pdf:
            messagebox.showwarning("Falta", "Seleccione el PDF de facturas a procesar.")
            return
        if not self.output_dir:
            messagebox.showwarning("Falta", "Seleccione la carpeta destino.")
            return

        logpath = configurar_logger()
        self.log(f"Iniciando: {os.path.basename(self.input_pdf)}")
        self.progress.start(10)
        self.root.update()

        escritos, fallidos = agrupar_y_escribir(self.input_pdf, self.output_dir)

        self.progress.stop()
        self.log(f"Proceso finalizado. Escritos: {escritos}. Fallidos: {len(fallidos)}")
        self.log(f"Log: {logpath}")
        messagebox.showinfo("Finalizado", f"Facturas generadas: {escritos}\nFallidos: {len(fallidos)}\nLog: {logpath}")

# -------------------- EJECUCIÓN --------------------
def main():
    root = tk.Tk()
    app = AppSeparador(root)
    root.mainloop()

if __name__ == "__main__":
    main()
