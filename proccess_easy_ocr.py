import fitz
import re
import os
from doctr.io import DocumentFile
from doctr.models import ocr_predictor
import time
import json
from pathlib import Path

# Fuzzy Matching
from rapidfuzz import process, fuzz

class ProcesadorFacturas:
    def __init__(self):
        # OPTIMIZACIÓN: modelo cargado una sola vez en __init__
        print("🔄 Cargando modelo OCR...")
        self.model = ocr_predictor(pretrained=True)
        print("✅ Modelo listo")

    def procesar_pdf(self, pdf_path):
        paginas_factura = self._filtrar_paginas(pdf_path)

        if not paginas_factura:
            print(f"⚠️  No se encontraron facturas en {pdf_path}")
            return []

        imagenes        = self._guardar_imagenes(pdf_path, paginas_factura)
        resultados_ocr  = self._ocr_imagenes(imagenes)

        facturas = []
        for i, resultado in enumerate(resultados_ocr):
            campos           = self._extraer_campos(resultado)
            campos['pagina'] = paginas_factura[i] + 1  # base 1
            campos['archivo'] = os.path.basename(pdf_path)
            facturas.append(campos)

        self._limpiar_imagenes(imagenes)
        if facturas:
            self._guardar_json(pdf_path, facturas)
        
        return facturas

    def _filtrar_paginas(self, pdf_path):
        """
        Detecta páginas con la palabra FACTURA (normal o con espacios)
        """
        paginas_factura = []
        doc = fitz.open(pdf_path)
        total = len(doc)
        print(f"\n📄 Filtrando {total} página(s) de: {os.path.basename(pdf_path)}")

        for page_num in range(total):
            page = doc[page_num]

            # ── Intento 1: texto nativo ──────────────────
            texto_nativo = page.get_text().strip()
            if texto_nativo:
                texto_upper = texto_nativo.upper()
                
                # Mejora: detectar tanto "FACTURA" como "F A C T U R A"
                tiene_factura = (
                    'FACTURA' in texto_upper or
                    'F A C T U R A' in texto_upper or
                    re.search(r'F\s+A\s+C\s+T\s+U\s+R\s+A', texto_upper)
                )
                
                tiene_clave = bool(re.search(r'\d{10,49}', texto_upper))
                tiene_ruc = bool(re.search(r'R\.?U\.?C\.?[:.\s]*\d{13}', texto_upper))

                if (tiene_factura and tiene_clave) or tiene_ruc:
                    paginas_factura.append(page_num)
                    print(f"  ✅ Página {page_num + 1}: FACTURA + clave (texto nativo)")
                else:
                    motivo = []
                    if not tiene_factura: motivo.append("sin FACTURA")
                    if not tiene_clave:   motivo.append("sin clave de dígitos")
                    print(f"  ❌ Página {page_num + 1}: {' y '.join(motivo)} (texto nativo)")
                continue

            # ── Intento 2: OCR para PDFs escaneados ──────
            img_path = f"temp_filtro_{page_num}_{abs(hash(pdf_path))}.png"
            pix = page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8))
            pix.save(img_path)

            try:
                doc_ocr = DocumentFile.from_images([img_path])
                result  = self.model(doc_ocr)

                texto_ocr = ' '.join(
                    w.value
                    for block in result.pages[0].blocks
                    for line  in block.lines
                    for w     in line.words
                ).upper()

                texto_sin_espacios = re.sub(r'\s+', '', texto_ocr)

                # Mejora: detectar "FACTURA" y "F A C T U R A"
                tiene_factura = (
                    'FACTURA' in texto_ocr or
                    'F A C T U R A' in texto_ocr or
                    re.search(r'F\s+A\s+C\s+T\s+U\s+R\s+A', texto_ocr)
                )
                
                tiene_clave = bool(re.search(r'\d{10,49}', texto_sin_espacios))

                if tiene_factura and tiene_clave:
                    paginas_factura.append(page_num)
                    clave = re.search(r'\d{10,49}', texto_sin_espacios)
                    print(f"  ✅ Página {page_num + 1}: FACTURA + clave "
                        f"({clave.group()[:10]}...) (OCR)")
                else:
                    motivo = []
                    if not tiene_factura: motivo.append("sin FACTURA")
                    if not tiene_clave:   motivo.append("sin clave de dígitos")
                    print(f"  ❌ Página {page_num + 1}: {' y '.join(motivo)} (OCR)")

            except Exception as e:
                print(f"  ⚠️  Página {page_num + 1}: error → {e}")

            finally:
                if os.path.exists(img_path):
                    os.remove(img_path)

        doc.close()
        print(f"\n📊 Filtro: {len(paginas_factura)}/{total} páginas válidas")
        return paginas_factura

    def _guardar_imagenes(self, pdf_path, paginas):
        """Guarda páginas filtradas como imágenes a mayor resolución para extracción"""
        imagenes = []
        doc = fitz.open(pdf_path)

        for page_num in paginas:
            page = doc[page_num]
            texto_pagina = page.get_text().upper()

            # Si la página contiene "FACTURA" → mayor resolución
            if 'FACTURA' in texto_pagina or re.search(r'F\s*A\s*C\s*T\s*U\s*R\s*A', texto_pagina):
                matrix = fitz.Matrix(2.8, 2.8)   # Alta resolución para FACTURA
                print(f"   📸 Página {page_num+1}: Alta resolución (FACTURA)")
            else:
                matrix = fitz.Matrix(1.8, 1.8)   # Resolución normal para otras páginas

            pix = page.get_pixmap(matrix=matrix)
            img_path = f"temp_ocr_{page_num}_{abs(hash(pdf_path))}.png"
            pix.save(img_path)
            imagenes.append(img_path)

        doc.close()
        return imagenes

    def _ocr_imagenes(self, imagenes):
        if not imagenes:
            return []
        doc    = DocumentFile.from_images(imagenes)
        result = self.model(doc)
        return result.pages

    def _buscar_razon_social_fuzzy(self, lines):
        patrones = [
            "Razon Social", "Razón Social:", "Razón Social/Nombres y Apellidos:",
            "RAZON SOCIAL", "RAZÓN SOCIAL:", "Razón Social / Nombres y Apellidos:",
            "Razón Social / Nombres :","Razón Social / Nombres:"
        ]
        
        mejor_score = 0
        mejor_texto = None

        for line in lines:
            match = process.extractOne(line, patrones, scorer=fuzz.partial_ratio)
            if match and match[1] > 82:  # Umbral ajustable
                # Extraer el texto después de los dos puntos o del patrón
                texto = line.strip()
                for patron in patrones:
                    if patron.lower() in texto.lower():
                        resultado = texto.split(":", 1)[-1].strip()
                        if len(resultado) > 3 and len(resultado) > len(mejor_texto or ""):
                            mejor_texto = resultado
                            mejor_score = match[1]
                        break
        return mejor_texto

    def _buscar_valor_total_fuzzy(self, lines):
        patrones = [
            "Valor Total", "Valor Total:", "VALOR TOTAL", "VALOR TOTAL:",
            "Total a Pagar", "TOTAL A PAGAR", "Total:", "TOTAL:", "VALOR TOTAL A PAGAR",
            "Total"
        ]
        
        mejor_valor = None
        mejor_score = 0

        for line in lines:
            match = process.extractOne(line, patrones, scorer=fuzz.partial_ratio)
            if match and match[1] > 78:
                numeros = re.findall(r'[\d,]+\.?\d*', line)
                if numeros:
                    valor = numeros[-1].replace(',', '')
                    if match[1] > mejor_score:
                        mejor_valor = valor
                        mejor_score = match[1]
        
        return mejor_valor

    def _buscar_identificacion_comprador_fuzzy(self, lines):
        patrones = [
            "Identificación", "Identificación:", "Identificacion", "Identificacion:",
            "RUC / CI:", "RUC/CI:", "Identificació", "Identificación:",
            "Identif", "CIRUC CLINTE:"
        ]
        
        mejor_valor = None
        mejor_score = 0

        for line in lines:
            if not line.strip():
                continue
                
            match = process.extractOne(line, patrones, scorer=fuzz.partial_ratio)
            
            if match and match[1] > 78:
                # Extraer números (mejorado)
                numeros = re.findall(r'[\d,]+\.?\d*', line)
                
                if numeros:
                    valor_str = numeros[-1].replace(',', '')
                    
                    # Actualizar si tiene mejor score
                    if match[1] > mejor_score:
                        mejor_valor = valor_str
                        mejor_score = match[1]
                        print(f"   🔍 Fuzzy Total encontrado: {valor_str} | Score: {match[1]} | Línea: {line[:60]}...")

        return mejor_valor

    def _extraer_campos(self, page_result):
        texto = ' '.join(
            w.value
            for block in page_result.blocks
            for line  in block.lines
            for w     in line.words
        )

        lines = []
        for block in page_result.blocks:
            for line_obj in block.lines:                    # ← Cambiado de 'line' a 'line_obj'
                line_text = ' '.join(w.value for w in line_obj.words).strip()
                if line_text:
                    lines.append(line_text)

        texto_sin_espacios = re.sub(r'\s+', '', texto)

        # print(f'DATOOOOOOS: {texto}')

        # ==================== VALOR TOTAL HÍBRIDO ====================
        valor_total = self._regex_search(
            r'(?:Valor\s+Total|VALOA\s+TOTAL|VALOR\s+TOTAL|Total\s+a\s+Pagar|TOTAL\s+A\s+PAGAR|VALOR\s+TOTAL\s+A\s+PAGAR)[:.\s\$]*([\d,]+\.?\d*)', 
            texto, 
            group=1
        )

        identificacion_comprador = self._regex_search(
                r'(?:Identificacion|Identificación|RUC/CI|C\.?I\.?|Identif\.|RUC\s*/?\s*CI)[:.\s]*(\d{10})', 
                texto, group=1
            ),

        # Si el regex no encuentra nada, usamos Fuzzy como respaldo
        if not valor_total or identificacion_comprador:
            valor_total = self._buscar_valor_total_fuzzy(lines)
            identificacion_comprador=self._buscar_identificacion_comprador_fuzzy(lines)

        clave_accesso = self._regex_search(r'\d{49}', texto_sin_espacios)
        print(f"CLAVE DE ACCESR: {clave_accesso}")

        ruc_extraido = None
        if clave_accesso and len(clave_accesso) == 49:
            ruc_extraido = clave_accesso[10:23]  # Posiciones 11-23
            print(f"RUC extraído de clave: {ruc_extraido}")
        else:
            print("Clave de acceso no válida o no encontrada")

        return {
            'autorizacion_json': clave_accesso,
            
            'identificacion_json': identificacion_comprador,
                        
            'fecha': self._regex_search(r'\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}', texto),
            
            'ruc': ruc_extraido,  # RUC suele estar en esos dígitos de la clave
            
            # Valor Total Híbrido
            'valor_total': self._regex_search(
                r'(?:Valor\s+Total|VALOR\s+TOTAL|Total\s+a\s+Pagar|TOTAL\s+A\s+PAGAR|VALOR\s+TOTAL\s+A\s+PAGAR)[:.\s\$]*([\d,]+\.?\d*)', 
                texto, 
                group=1
            ),

            # Fuzzy
            'razon_social': self._buscar_razon_social_fuzzy(lines),
        }


    def _regex_search(self, pattern, text, group=0):
        match = re.search(pattern, text)
        return match.group(group) if match else None

    def _limpiar_imagenes(self, imagenes):
        for img in imagenes:
            if os.path.exists(img):
                os.remove(img)

    def _guardar_json(self, pdf_path, facturas):
        """Guarda los resultados en múltiples formatos"""
        stem = Path(pdf_path).stem 
        # Estructura completa recomendada
        documento_json = {
            "archivo": os.path.basename(pdf_path),
            "total_paginas": len(fitz.open(pdf_path)),  # total de páginas del PDF
            "facturas_encontradas": len(facturas),
            "facturas": []
        }

        for factura in facturas:
            factura_completa = {
                "pagina": factura.get('pagina'),
                "autorizacion_json": factura.get('autorizacion_json'),
                "identificacion_comprador_json":factura.get('identificacion_json'),
                "razon_social":factura.get('razon_social'),
                "fecha": factura.get('fecha'),
                "ruc": factura.get('ruc'),
                "valor_total": factura.get('valor_total')

            }
            documento_json["facturas"].append(factura_completa)

        # Guardar JSON completo (formato bonito)
        ruta_json = f"json_files/clave_{stem}.json"
        
        with open(ruta_json, 'w', encoding='utf-8') as f:
            json.dump(documento_json, f, indent=4, ensure_ascii=False)

        print(f"✅ JSON completo guardado → {ruta_json}")
        return ruta_json

# ── Uso ────────────────────────────────────────────
# if __name__ == "__main__":
#     inicio = time.time()
#     procesador = ProcesadorFacturas()
#     resultados = procesador.procesar_pdf("KAREN CASTRO 466.99.pdf")

#     print(f"\n{'═'*50}")
#     print(f"📊 {len(resultados)} factura(s) encontrada(s)")
#     print(f"{'═'*50}")

#     for factura in resultados:
#         print(f"\n📄 Página {factura['pagina']} — {factura['archivo']}")
#         print(f"   Clave acceso  : {factura['clave_acceso']}")
#         print(f"   Número        : {factura['numero_factura']}")
#         print(f"   Fecha         : {factura['fecha']}")
#         print(f"   Valor total   : ${factura['valor_total']}")
#         print(f"   RUC           : {factura['ruc']}")

#     fin = time.time()
#     minutos = (fin - inicio) / 60
#     print(f"\n⏱️ Tiempo total: {fin - inicio:.2f} segundos")
#     print(f"\n⏱️ Tiempo total: {minutos:.2f} minutos")
