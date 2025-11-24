#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
procesar_albaranes.py (versión actualizada)
- OCR focalizado en el rectángulo superior-izq (zona completa, sin recortar a mitad)
- Preprocesado más agresivo (resize x4, UnsharpMask, median+gauss)
- Dos pasadas OCR con distintas configs y whitelist
- Fallbacks: búsqueda de 4 dígitos, búsqueda en página completa
- Guarda imagen de caso fallido para diagnóstico
Requisitos: PyMuPDF (fitz), Pillow, pytesseract, tkinter
Asegúrate de tesseract.exe en:
C:\Program Files\Tesseract-OCR\tesseract.exe
"""

import os
import re
import shutil
import logging
from datetime import datetime
from io import BytesIO

import fitz  # PyMuPDF
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
import pytesseract

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ----------------------------- CONFIG -----------------------------
# Ruta a tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Rectángulo en cm desde el borde superior-izq (como nos has dado)
RECT_LEFT_CM = 1.1
RECT_TOP_CM = 5.6
RECT_RIGHT_CM = 7.4
RECT_BOTTOM_CM = 6.9

# Padding extra en cm (para asegurar que no cortamos)
PAD_CM = 0.2

# DPI para renderizado (alto para mejor OCR)
RENDER_DPI = 300

# Factor de escalado en preprocess (x4 recomendado)
SCALE_FACTOR = 4

# Carpeta para guardar imágenes de fallidos
FAIL_IMG_DIR = "logs/fails_images"

# Regex principales (adaptadas)
REGEX_PATTERNS = [
    re.compile(r'Albar[aá]n[:\s]*A\s*(\d{2})\s+(\d{4})', re.IGNORECASE),  # "Albarán: A25  1608"
    re.compile(r'A\s*(\d{2})\s+(\d{4})', re.IGNORECASE),                 # "A25 1608"
    re.compile(r'([A]\d{2})\D*?(\d{4})'),                               # fallback "A25 ... 1608"
]

# ------------------------------------------------------------------

def configurar_logger():
    base_dir = os.getcwd()
    logs_dir = os.path.join(base_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    os.makedirs(os.path.join(logs_dir, "fails_images"), exist_ok=True)
    log_filename = datetime.now().strftime("procesar_albaranes_%Y%m%d_%H%M%S.log")
    log_path = os.path.join(logs_dir, log_filename)
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.info("=== INICIO PROCESO DE ALBARANES ===")
    return log_path

def cm_to_points(cm):
    return cm * (72.0 / 2.54)

def render_region_image_full(pdf_path):
    """
    Renderiza la región completa (con padding) de la primera página y devuelve PIL.Image (RGB).
    """
    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(0)
    except Exception as e:
        logging.error(f"No se pudo abrir {pdf_path}: {e}")
        return None

    # calcular rect en puntos
    left = cm_to_points(max(0.0, RECT_LEFT_CM - PAD_CM))
    top = cm_to_points(max(0.0, RECT_TOP_CM - PAD_CM))
    right = cm_to_points(RECT_RIGHT_CM + PAD_CM)
    bottom = cm_to_points(RECT_BOTTOM_CM + PAD_CM)

    clip = fitz.Rect(left, top, right, bottom)

    mat = fitz.Matrix(RENDER_DPI / 72.0, RENDER_DPI / 72.0)
    try:
        pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
    except Exception as e:
        logging.error(f"Error renderizando imagen de {pdf_path}: {e}")
        return None

    img_bytes = pix.tobytes("png")
    img = Image.open(BytesIO(img_bytes)).convert("RGB")
    return img

def preprocess_image_for_ocr(img: Image.Image) -> Image.Image:
    """
    Preprocesado intensivo:
    - escala (SCALE_FACTOR)
    - convierte a gris, aumenta contraste y nitidez
    - median + gaussian blur ligero y unsharp
    - conversión a B/W con umbral adaptado
    """
    # convertir a RGB para consistencia
    img = img.convert("RGB")

    # escalar
    w, h = img.size
    img = img.resize((int(w * SCALE_FACTOR), int(h * SCALE_FACTOR)), Image.BICUBIC)

    # convertir a gris
    gray = ImageOps.grayscale(img)

    # aumentar contraste
    enh = ImageEnhance.Contrast(gray)
    gray = enh.enhance(1.5)

    # filtro mediana para ruido
    gray = gray.filter(ImageFilter.MedianFilter(size=3))

    # suavizado ligero antes de unsharp
    gray = gray.filter(ImageFilter.GaussianBlur(radius=1))

    # unsharp mask para realzar bordes
    gray = gray.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))

    # umbral adaptativo simple: usar la media del histograma
    hist = gray.histogram()
    pixels = sum(hist)
    if pixels == 0:
        return gray
    mean = sum(i * hist[i] for i in range(256)) / pixels
    # elegir factor <=1 para no perder trazos finos
    bw = gray.point(lambda x: 255 if x > mean * 0.95 else 0)

    return bw

def ocr_passes_and_texts(img: Image.Image):
    """
    Ejecuta varias pasadas OCR con distintas configs y devuelve texto combinado y textos individuales.
    """
    texts = []
    # Preprocesar imagen (devuelve B/W PIL)
    proc = preprocess_image_for_ocr(img)

    # Pass 1: psm 6, whitelist A + dígitos + simbolos
    try:
        config1 = r'--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789: /'
        t1 = pytesseract.image_to_string(proc, lang='spa', config=config1)
    except Exception as e:
        logging.error(f"OCR pass1 falló: {e}")
        t1 = ""

    texts.append(t1)

    # Pass 2: psm 7 (single line) para casos en una única línea
    try:
        config2 = r'--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789: /'
        t2 = pytesseract.image_to_string(proc, lang='spa', config=config2)
    except Exception as e:
        logging.error(f"OCR pass2 falló: {e}")
        t2 = ""

    texts.append(t2)

    # También extraer con psm 4 (varias líneas)
    try:
        config3 = r'--psm 4'
        t3 = pytesseract.image_to_string(proc, lang='spa', config=config3)
    except Exception as e:
        t3 = ""

    texts.append(t3)

    # Combinar: unir eliminando saltos innecesarios
    combined = "\n".join([t.strip() for t in texts if t and t.strip()])
    return combined, texts

def extract_albaran_from_text(text):
    """
    Busca el patrón dentro del texto (varias regex). Devuelve número 4 dígitos si lo encuentra.
    Se normaliza el texto eliminando saltos de línea entre token adyacentes para formar 'Albarán: A25 1608'.
    """
    if not text:
        return None, ""

    # Normalizar: unir líneas próximas, eliminar multiple espacios
    norm = re.sub(r'\r\n|\n', ' ', text)
    norm = re.sub(r'\s{2,}', ' ', norm).strip()
    logging.info(f"Texto OCR combinado (normalize): {norm[:400]}")

    # Intentar patrones
    for pat in REGEX_PATTERNS:
        m = pat.search(norm)
        if m:
            if len(m.groups()) >= 2:
                year = m.group(1)
                num = re.sub(r'\D', '', m.group(2))
                if len(num) >= 3:
                    # tomar últimos 4 si sobra
                    num = num[-4:].zfill(4)
                    return num, norm
            else:
                g1 = m.group(1)
                digits = re.sub(r'\D', '', g1)
                if len(digits) >= 3:
                    digits = digits[-4:].zfill(4)
                    return digits, norm

    # fallback: primer número de 4 cifras
    m2 = re.search(r'\b(\d{4})\b', norm)
    if m2:
        return m2.group(1), norm

    return None, norm

def renombrar_y_copiar(original_path, numero, destino_dir):
    os.makedirs(destino_dir, exist_ok=True)
    nuevo_nombre = f"Albarán nº {numero}.pdf"
    nueva_ruta = os.path.join(destino_dir, nuevo_nombre)
    contador = 1
    while os.path.exists(nueva_ruta):
        nuevo_nombre = f"Albarán nº {numero} ({contador}).pdf"
        nueva_ruta = os.path.join(destino_dir, nuevo_nombre)
        contador += 1
    shutil.copy2(original_path, nueva_ruta)
    logging.info(f"{os.path.basename(original_path)} -> {nuevo_nombre}")
    return nueva_ruta

# Interfaz GUI (similar a versión anterior, con barra de progreso y texto)
class SimpleApp:
    def __init__(self, root):
        self.root = root
        root.title("Procesar Albaranes")
        root.geometry("560x200")
        root.resizable(False, False)

        self.label_status = tk.Label(root, text="Cargando aplicación...", font=("Segoe UI", 11))
        self.label_status.pack(pady=8)

        frame_btns = tk.Frame(root)
        frame_btns.pack(pady=6)
        self.btn_start = tk.Button(frame_btns, text="Iniciar procesamiento", command=self.start_process, width=18)
        self.btn_start.pack(side=tk.LEFT, padx=6)
        self.btn_quit = tk.Button(frame_btns, text="Salir", command=root.quit, width=10)
        self.btn_quit.pack(side=tk.LEFT, padx=6)

        self.progress = ttk.Progressbar(root, orient='horizontal', mode='determinate', length=520)
        self.progress.pack(pady=6)
        self.progress.pack_forget()

        self.text_area = tk.Text(root, height=6, width=72)
        self.text_area.pack(padx=6, pady=4)
        self.text_area.insert(tk.END, "Pulse 'Iniciar procesamiento' para seleccionar carpetas.\n")
        self.text_area.config(state=tk.DISABLED)
        root.update()

    def log_to_text(self, msg):
        self.text_area.config(state=tk.NORMAL)
        self.text_area.insert(tk.END, msg + "\n")
        self.text_area.see(tk.END)
        self.text_area.config(state=tk.DISABLED)
        self.root.update()

    def start_process(self):
        messagebox.showinfo("Paso 1", "Seleccione la carpeta con los ALBARANES a renombrar.")
        carpeta_origen = filedialog.askdirectory(title="Seleccione la carpeta de albaranes a renombrar")
        if not carpeta_origen:
            messagebox.showwarning("Cancelado", "No seleccionó carpeta origen.")
            return
        messagebox.showinfo("Paso 2", "Seleccione la carpeta DESTINO donde se guardarán los albaranes renombrados.")
        carpeta_destino = filedialog.askdirectory(title="Seleccione la carpeta destino")
        if not carpeta_destino:
            messagebox.showwarning("Cancelado", "No seleccionó carpeta destino.")
            return

        self.label_status.config(text="Procesando... (no cerrar la ventana)")
        self.progress.pack()
        archivos = [f for f in os.listdir(carpeta_origen) if f.lower().endswith(".pdf")]
        total = len(archivos)
        self.progress['maximum'] = total
        self.progress['value'] = 0
        self.root.update()

        logging.info(f"Carpeta origen: {carpeta_origen}")
        logging.info(f"Carpeta destino: {carpeta_destino}")
        logging.info(f"Total archivos: {total}")

        procesados = 0
        fallidos = []

        for idx, archivo in enumerate(archivos, start=1):
            self.log_to_text(f"[{idx}/{total}] Procesando: {archivo}")
            ruta = os.path.join(carpeta_origen, archivo)
            img = render_region_image_full(ruta)
            if img is None:
                logging.error(f"No se pudo renderizar {archivo}")
                fallidos.append(archivo)
                self.progress['value'] = idx
                self.root.update()
                continue

            # Ejecutar OCR con múltiples pasadas
            combined_text, texts = ocr_passes_and_texts(img)
            numero, norm_text = extract_albaran_from_text(combined_text)

            # Si no se detecta, intento ampliar el OCR a toda la página (fallback)
            if not numero:
                logging.info("No detectado en recorte; intentando OCR de página completa como fallback.")
                try:
                    doc = fitz.open(ruta)
                    # render full page at high dpi
                    page = doc.load_page(0)
                    mat = fitz.Matrix(RENDER_DPI / 72.0, RENDER_DPI / 72.0)
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    full_img = Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")
                    combined_full, texts_full = ocr_passes_and_texts(full_img)
                    numero, norm_text = extract_albaran_from_text(combined_full)
                except Exception as e:
                    logging.error(f"Fallback página completa falló: {e}")
                    numero = None

            if numero:
                renombrar_y_copiar(ruta, numero, carpeta_destino)
                procesados += 1
                self.log_to_text(f"  → Albarán detectado: {numero}")
            else:
                logging.warning(f"No se detectó número en {archivo}. OCR zona: {combined_text.strip()[:200]}")
                fallidos.append(archivo)
                # Guardar imagen de zona para diagnóstico
                try:
                    base_fail = os.path.join("logs", "fails_images", f"{os.path.splitext(archivo)[0]}.png")
                    img.save(base_fail)
                    logging.info(f"Imagen de fallo guardada en: {base_fail}")
                except Exception as e:
                    logging.error(f"No se pudo guardar imagen de fallo: {e}")
                self.log_to_text(f"  ⚠ No detectado (imagen guardada para revisión)")

            self.progress['value'] = idx
            self.root.update()

        logging.info(f"Procesados: {procesados}/{total}")
        logging.info(f"Fallidos: {len(fallidos)}")
        if fallidos:
            logging.warning("Lista de fallidos:")
            for f in fallidos:
                logging.warning(f" - {f}")

        messagebox.showinfo("Proceso finalizado",
                            f"Albaranes procesados: {procesados} de {total}\n"
                            f"Se ha generado un log en la carpeta 'logs' del ejecutable.")
        self.label_status.config(text="Procesamiento completado.")
        self.log_to_text("Proceso completado.")
        self.root.update()

def main():
    log_path = configurar_logger()
    root = tk.Tk()
    app = SimpleApp(root)
    root.update()
    root.mainloop()
    logging.info("Aplicación cerrada por el usuario.")
    logging.info("Log: " + log_path)

if __name__ == "__main__":
    main()
