import easyocr
import pandas as pd
import numpy as np
from pathlib import Path
from pdf2image import convert_from_path
import warnings
import time
import cv2
import json

warnings.filterwarnings('ignore')

import os
import certifi
import ssl

# Solución para problemas de certificados SSL
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

def preprocess_image(img_pil):
    # """Limpieza fuerte con OpenCV para documentos escaneados"""
    # # PIL → OpenCV
    # img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    
    # # 1. Escala de grises
    # gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # # 2. Mejorar contraste (muy importante)
    # clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    # enhanced = clahe.apply(gray)
    
    # # 3. Reducción de ruido
    # denoised = cv2.fastNlMeansDenoising(enhanced, h=7, searchWindowSize=21, templateWindowSize=7)
    
    # # 4. Binarización adaptativa (mejor que Otsu en documentos)
    # binary = cv2.adaptiveThreshold(
    #     denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    #     cv2.THRESH_BINARY, 11, 2
    # )
    
    # # 5. Enderezar la imagen (deskew)
    # coords = np.column_stack(np.where(binary > 0))
    # if len(coords) > 0:
    #     angle = cv2.minAreaRect(coords)[-1]
    #     if angle < -45:
    #         angle = -(90 + angle)
    #     else:
    #         angle = -angle
    #     (h, w) = binary.shape
    #     center = (w // 2, h // 2)
    #     M = cv2.getRotationMatrix2D(center, angle, 1.0)
    #     binary = cv2.warpAffine(binary, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    
    # # Volver a RGB para EasyOCR (prefiere color)
    # final = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
    # return final

    """Tu preprocesamiento actual pero optimizado para números"""
    img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # CLAHE para mejorar contraste en números pequeños
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
        
        # Redimensionar si es muy pequeña (crítico para números de 49 dígitos)
    h, w = enhanced.shape
    if h < 1200:  # Si es menor a A4 a 300dpi, escalar
        enhanced = cv2.resize(enhanced, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        
        # Denoising suave (no agresivo para no borrar números)
    denoised = cv2.fastNlMeansDenoising(enhanced, h=10)
        
        # Binarización adaptativa (mejor que Otsu para documentos)
    binary = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )
        
        # Volver a RGB (EasyOCR prefiere color)
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)



class ProcesadorEasyOCR:
    def __init__(self):
        print("🔄 Cargando modelo de EasyOCR (solo la primera vez descarga ~100MB)...")
        # Idioma español, modo CPU (más estable)
        self.reader = easyocr.Reader(['es'])
        print("✅ Modelo listo")
    
    def extraer_campos(self, texto_completo):
        """Extrae campos clave con regex simple"""
        import re
        
        texto = texto_completo.upper()
        datos = {}
        
        # Autorización (37-49 dígitos seguidos)
        match = re.search(r'(\d{49})', texto, re.IGNORECASE)

        datos['autorizacion_json'] = match.group(1) if match else None
        
        # RUC (13 dígitos)
        match = re.search(r'(\d{13})', texto)
        datos['ruc'] = match.group(1) if match else None

        #   IDENTIFICACION
        # match = re.search(r'(\d{10})', texto)
        # #Identificación
        # datos['identificacion_json'] = match.group(1) if match else None
        match_id = re.search(r'(?:IDENTIFICACION|Identificación|CEDULA|RUC)[^\d]*([0-9OIlSB]{10})', texto)

        if match_id:
            # Usamos la limpieza para asegurar que sean números reales
            id_sucia = match_id.group(1)
            id_limpia = id_sucia.replace('O','0').replace('I','1').replace('l','1').replace('S','5').replace('B','8')
            datos['identificacion_json'] = id_limpia
        else:
            datos['identificacion_json'] = None
        
        # Factura formato 001-001-000000001
        match = re.search(r'(\d{3}-\d{3}-\d{9})', texto)
        datos['numero_factura'] = match.group(1) if match else None
        
        # Total (busca $ seguido de número o número con decimales al final)
        match = re.search(r'(?:VALOR\s+TOTAL|TOTAL)[^\d]*[\$]?\s*(\d[\d\.,]*\d{2})', texto, re.IGNORECASE)
        if match:
            valor_str = match.group(1)
            # Limpiar formato (1.234,56 → 1234.56)
            valor_str = valor_str.replace('.', '').replace(',', '.') if ',' in valor_str else valor_str
            datos['total'] = float(valor_str)
        else:
            datos['total'] = None
        # datos['total'] = match.group(1) if match else None
        
        return datos
    
    def procesar_pdf(self, ruta_pdf):
        """Procesa un PDF completo"""
        nombre = Path(ruta_pdf).name
        print(f"\n📄 Procesando: {nombre}")
        
        try:
            # PDF -> Imagen(es)
            imagenes = convert_from_path(ruta_pdf, dpi=300)
            
            resultados = []
            lista_claves = []
            for num, img_pil in enumerate(imagenes, 1):
                print(f"  Página {num}/{len(imagenes)}...", end=" ")
                
                # ********Convertir PIL -> Numpy (RGB)
                # img_array = np.array(img_pil)
                img_array = preprocess_image(img_pil)
                
                # OCR (detail=0 devuelve solo texto, detail=1 devuelve coordenadas)
                # Para flujo básico usamos detail=0 (más rápido)
                texto_detectado = self.reader.readtext(img_array, detail=0, paragraph=True)
                
                # Unir todo el texto
                texto_plano = " ".join(texto_detectado)
                
                # Extraer campos
                campos = self.extraer_campos(texto_plano)
                
                resultados.append({
                    'archivo': nombre,
                    'pagina': num,
                    **campos,
                    'texto_completo': texto_plano[:200] + "..."  # Preview
                    
                })

                if campos['autorizacion_json']:
                    lista_claves.append({
                        "pdf_nombre": nombre,
                        # "pagina": num,
                        "autorizacion_json": campos['autorizacion_json'],
                        "ruc_json": campos['ruc'],
                        "identificacion_json": campos['identificacion_json'],
                        "total_json": campos['total']
                        # "total": campos['total']

                    })
                
                print(f"✓ ({len(texto_plano)} caracteres)")
            
            # ====================== GUARDAR RESULTADOS ======================
            
            # 2. JSON con solo las claves (para enviar a la API)
            if lista_claves:
                ruta_json = f"json_files/claves_{Path(nombre).stem}.json"
                with open(ruta_json, "w", encoding="utf-8") as f:
                    json.dump(lista_claves, f, indent=2, ensure_ascii=False)
                print(f"✅ {len(lista_claves)} clave(s) guardada(s) en → {ruta_json}")
            else:
                print("⚠️  No se encontró ninguna clave de acceso")

            return lista_claves
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return [{
                'archivo': nombre,
                'pagina': 0,
                'autorizacion_json': None,
                'ruc_json': None,
                'numero_factura': None,
                'total': None,
                'error': str(e)
            }]

