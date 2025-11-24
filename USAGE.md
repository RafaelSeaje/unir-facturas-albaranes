# Instrucciones de uso

## 1. Separar facturas (separar_facturas.py)

1. Abrir el ejecutable o correr:
   ```
   python src/separar_facturas.py
   ```
2. Seleccionar el PDF origen que contiene todas las facturas.
3. Elegir carpeta destino.
4. Pulsar "INICIAR SEPARACIÓN".
5. El sistema generará:
   - un PDF por factura
   - log en `logs/separar_facturas.log`

---

## 2. Renombrar albaranes (procesar_albaranes.py)

1. Ejecutar:
   ```
   python src/procesar_albaranes.py
   ```
2. Seleccionar carpeta con albaranes.
3. Confirmar procesamiento.
4. Los PDFs se renombrarán según su número y fecha.

---

## 3. Unir facturas + albaranes (unir_facturas_albaranes.py)

En desarrollo.  
El funcionamiento final será:

1. Leer facturas ya separadas y renombradas.  
2. Buscar sus albaranes correspondientes.
3. Generar un PDF fusionado por factura.

---

## Notas importantes

- Tesseract debe estar instalado en el sistema.  
- Los ejecutables se generan en `dist/`.
