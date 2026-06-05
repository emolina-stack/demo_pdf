import fitz
import re
import os
import cv2
import numpy as np
from PIL import Image
from doctr.io import DocumentFile
from doctr.models import ocr_predictor
import time
import json
from pathlib import Path

# Fuzzy Matching
from rapidfuzz import process, fuzz


class ProcesadorFacturas:
    def __init__(self):
        print("🔄 Cargando modelo OCR...")
        self.model = ocr_predictor(pretrained=True)
        print("✅ Modelo listo")

    def preprocess_image_fuerte(self, img_pil):
        """Preprocesamiento ULTRA para PDFs de iLovePDF"""
        img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        clahe = cv2.createCLAHE(clipLimit=7.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        binary = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 9, 4
        )
        
        binary = cv2.resize(binary, None, fx=2.8, fy=2.8, interpolation=cv2.INTER_CUBIC)
        binary = cv2.GaussianBlur(binary, (3, 3), 0)
        
        kernel = np.ones((2,2), np.uint8)
        binary = cv2.dilate(binary, kernel, iterations=1)
        
        return cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)

    def procesar_pdf(self, pdf_path):
        paginas_factura = self._filtrar_paginas(pdf_path)

        if not paginas_factura:
            print(f"⚠️  No se encontraron facturas en {pdf_path}")
            return []

        imagenes = self._guardar_imagenes(pdf_path, paginas_factura)
        resultados_ocr = self._ocr_imagenes(imagenes)

        # === AGRUPACIÓN Y UNIFICACIÓN DE FACTURAS MULTI-PÁGINA ===
        facturas = self._agrupar_y_unificar_facturas(resultados_ocr, paginas_factura, pdf_path)

        self._limpiar_imagenes(imagenes)
        if facturas:
            self._guardar_json(pdf_path, facturas)
        
        return facturas

    def _filtrar_paginas(self, pdf_path):
        """Filtrado mejorado y tolerante"""
        paginas_factura = []
        doc = fitz.open(pdf_path)
        total = len(doc)
        print(f"\n📄 Analizando {total} página(s) de: {os.path.basename(pdf_path)}")

        for page_num in range(total):
            page = doc[page_num]
            motivo = []

            # Texto nativo
            texto_nativo = page.get_text().strip()
            if texto_nativo:
                upper = texto_nativo.upper()
                sin_espacios = re.sub(r'\s+', '', upper)

                tiene_factura = 'FACTURA' in upper or re.search(r'F\s*A\s*C\s*T\s*U\s*R\s*A', upper)
                tiene_clave = bool(re.search(r'\d{49}', sin_espacios))
                tiene_ruc = bool(re.search(r'R\.?U\.?C\.?[:.\s]*\d{13}', upper))
                tiene_num_factura = bool(re.search(r'\d{3}-\d{3}-\d{9}', upper))

                if tiene_factura or tiene_clave or tiene_ruc or tiene_num_factura:
                    paginas_factura.append(page_num)
                    print(f"  ✅ Página {page_num + 1}: Detectada (nativo)")
                    continue

            # OCR con alta resolución
            img_path = f"temp_filtro_{page_num}_{abs(hash(pdf_path))}.png"
            pix = page.get_pixmap(matrix=fitz.Matrix(2.8, 2.8))
            pix.save(img_path)

            try:
                img_pil = Image.open(img_path)
                img_procesada = self.preprocess_image_fuerte(img_pil)
                cv2.imwrite(img_path, cv2.cvtColor(img_procesada, cv2.COLOR_RGB2BGR))

                doc_ocr = DocumentFile.from_images([img_path])
                result = self.model(doc_ocr)

                texto_ocr = ' '.join(w.value for block in result.pages[0].blocks
                                   for line in block.lines for w in line.words)
                upper = texto_ocr.upper()
                sin_espacios = re.sub(r'\s+', '', upper)

                print(f"   📝 P{page_num+1} OCR: {len(texto_ocr)} chars | FACTURA?: {'SÍ' if 'FACTURA' in upper else 'NO'}")

                tiene_factura = 'FACTURA' in upper or re.search(r'F\s*A\s*C\s*T\s*U\s*R\s*A', upper)
                tiene_clave = bool(re.search(r'\d{49}', sin_espacios))
                tiene_ruc = bool(re.search(r'R\.?U\.?C\.?[:.\s]*\d{13}', upper))
                tiene_num_factura = bool(re.search(r'\d{3}-\d{3}-\d{9}', upper))

                if tiene_factura or tiene_clave or tiene_ruc or tiene_num_factura:
                    paginas_factura.append(page_num)
                    print(f"  ✅ Página {page_num + 1}: ACEPTADA (OCR)")
                else:
                    print(f"  ❌ Página {page_num + 1}: descartada")

            finally:
                if os.path.exists(img_path):
                    os.remove(img_path)

        doc.close()
        print(f"📊 Seleccionadas {len(paginas_factura)}/{total} páginas\n")
        return paginas_factura

    def _guardar_imagenes(self, pdf_path, paginas):
        """Guarda imágenes con alta resolución"""
        imagenes = []
        doc = fitz.open(pdf_path)

        for page_num in paginas:
            page = doc[page_num]
            matrix = fitz.Matrix(3.0, 3.0)
            print(f"   📸 Página {page_num+1}: Resolución alta (3.0x)")

            pix = page.get_pixmap(matrix=matrix)
            img_path = f"temp_ocr_{page_num}_{abs(hash(pdf_path))}.png"
            pix.save(img_path)
            
            img_pil = Image.open(img_path)
            img_procesada = self.preprocess_image_fuerte(img_pil)
            cv2.imwrite(img_path, cv2.cvtColor(img_procesada, cv2.COLOR_RGB2BGR))
            
            imagenes.append(img_path)

        doc.close()
        return imagenes

    def _ocr_imagenes(self, imagenes):
        if not imagenes:
            return []
        doc = DocumentFile.from_images(imagenes)
        result = self.model(doc)
        return result.pages

    def _agrupar_y_unificar_facturas(self, resultados_ocr, paginas_indices, pdf_path):
        """Agrupa páginas por factura y unifica campos (especialmente valor_total)"""
        facturas = []
        factura_actual = None
        clave_actual = None

        for i, resultado in enumerate(resultados_ocr):
            pagina_num = paginas_indices[i] + 1
            campos = self._extraer_campos(resultado)
            
            campos['pagina'] = pagina_num
            campos['archivo'] = os.path.basename(pdf_path)

            clave_encontrada = campos.get('autorizacion_json')

            if clave_encontrada and clave_encontrada != clave_actual:
                # Nueva factura
                if factura_actual is not None:
                    facturas.append(factura_actual)
                
                factura_actual = campos.copy()
                clave_actual = clave_encontrada
                print(f"   📌 Nueva factura iniciada → Clave: {clave_actual[:25]}...")
            elif factura_actual is not None:
                # Misma factura → unificar campos
                for campo in ['valor_total', 'razon_social', 'identificacion_json', 'fecha', 'ruc']:
                    if campos.get(campo) and not factura_actual.get(campo):
                        factura_actual[campo] = campos.get(campo)
                        print(f"   🔄 Campo '{campo}' unificado desde página {pagina_num}")

        if factura_actual is not None:
            facturas.append(factura_actual)

        print(f"✅ Se procesaron {len(facturas)} facturas completas (multi-página)\n")
        return facturas

    def _extraer_campos(self, page_result):
        texto = ' '.join(
            w.value for block in page_result.blocks
                    for line in block.lines for w in line.words
        )

        lines = [' '.join(w.value for w in line.words).strip() 
                for block in page_result.blocks for line in block.lines if line.words]

        texto_sin_espacios = re.sub(r'\s+', '', texto)

        valor_total = self._regex_search(
            r'(?:Valor\s+Total|VALOR\s+TOTAL|VALOR\s+TOTAL\s+USD|VALOA?\s+TOTAL|Total\s+a\s+Pagar|TOTAL\s+A\s+PAGAR|SUBTOTAL\s+SIN\s+IMPUESTOS)[:.\s\$]*([\d,]+\.?\d*)', 
            texto, group=1
        )

        if not valor_total:
            valor_total = self._buscar_valor_total_fuzzy(lines)

        identificacion_json = self._regex_search(
            r'(?:Identificacion|Identificación|RUC/CI|C\.?I\.?|RUC\s*/?\s*CI)[:.\s]*(\d{10,13})', 
            texto, group=1
        )

        if not identificacion_json:
            identificacion_json = self._buscar_identificacion_comprador_fuzzy(lines)

        return {
            'autorizacion_json': self._regex_search(r'\d{49}', texto_sin_espacios),
            'identificacion_json': identificacion_json,
            'numero_factura': self._regex_search(r'\d{3}-\d{3}-\d{9}', texto),
            'fecha': self._regex_search(r'\d{2}/\d{2}/\d{4}', texto),
            'ruc': self._regex_search(r'(?:RUC|R\.?U\.?C\.?)[:.\s]*(\d{13})', texto, group=1),
            'valor_total': valor_total,
            'razon_social': self._buscar_razon_social_fuzzy(lines),
        }

    def _regex_search(self, pattern, text, group=0, flags=0):
        if not text:
            return None
        match = re.search(pattern, text, flags)
        return match.group(group).strip() if match else None

    # ==================== FUNCIONES FUZZY ====================
    def _buscar_razon_social_fuzzy(self, lines):
        patrones = ["Razon Social", "Razón Social", "Razón Social/Nombres y Apellidos", "RAZON SOCIAL"]
        mejor_texto = None
        mejor_score = 0

        for line in lines:
            match = process.extractOne(line, patrones, scorer=fuzz.partial_ratio)
            if match and match[1] > 80:
                texto = line.strip()
                resultado = texto.split(":", 1)[-1].strip()
                if len(resultado) > 3 and len(resultado) > len(mejor_texto or ""):
                    mejor_texto = resultado
        return mejor_texto

    def _buscar_valor_total_fuzzy(self, lines):
        patrones = ["Valor Total", "VALOR TOTAL", "Total a Pagar", "TOTAL A PAGAR", "Total"]
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
        patrones = ["Identificación", "Identificacion", "RUC / CI", "RUC/CI"]
        mejor_valor = None
        mejor_score = 0

        for line in lines:
            if not line.strip(): continue
            match = process.extractOne(line, patrones, scorer=fuzz.partial_ratio)
            if match and match[1] > 78:
                numeros = re.findall(r'\d{10,13}', line)
                if numeros:
                    valor_str = numeros[-1]
                    if match[1] > mejor_score:
                        mejor_valor = valor_str
                        mejor_score = match[1]
        return mejor_valor

    def _limpiar_imagenes(self, imagenes):
        for img in imagenes:
            if os.path.exists(img):
                os.remove(img)

    def _guardar_json(self, pdf_path, facturas):
        stem = Path(pdf_path).stem 
        documento_json = {
            "archivo": os.path.basename(pdf_path),
            "total_paginas": len(fitz.open(pdf_path)),
            "facturas_encontradas": len(facturas),
            "facturas": []
        }

        for factura in facturas:
            documento_json["facturas"].append({
                "pagina": factura.get('pagina'),
                "autorizacion_json": factura.get('autorizacion_json'),
                "identificacion_json": factura.get('identificacion_json'),
                "razon_social": factura.get('razon_social'),
                "fecha": factura.get('fecha'),
                "ruc": factura.get('ruc'),
                "valor_total": factura.get('valor_total')
            })

        ruta_json = f"json_files/clave_{stem}.json"
        
        with open(ruta_json, 'w', encoding='utf-8') as f:
            json.dump(documento_json, f, indent=4, ensure_ascii=False)

        print(f"✅ JSON completo guardado → {ruta_json}")
        return ruta_json