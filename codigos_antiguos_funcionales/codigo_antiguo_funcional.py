from pathlib import Path
from pdf2image import convert_from_path

import easyocr
import pandas as pd
import numpy as np
import os
import certifi
import time
import ssl
import cv2
import warnings
warnings.filterwarnings('ignore')

# Solución para problemas de certificados SSL
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# Configuración

# pdf_path = "files/Ceci by iScanner.pdf" #2pag
# pdf_path = "files/NAEL LAMAN LUZURIAGA 230.89.pdf" #11pag
# pdf_path = "files/JACQUELINE JOHNSON 2_compressed.pdf" #    27pag
pdf_path = "files/KAREN CASTRO 466.99.pdf"   #9pag
# pdf_path = "files/Edison Molina_demo.pdf"


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

        datos['autorizacion'] = match.group(1) if match else None
        
        # RUC (13 dígitos)
        match = re.search(r'(\d{13})', texto)
        datos['ruc'] = match.group(1) if match else None
        
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
            for num, img_pil in enumerate(imagenes, 1):
                print(f"  Página {num}/{len(imagenes)}...", end=" ")
                
                # Convertir PIL -> Numpy (RGB)
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
                    'texto_completo': texto_plano[:200] + "...",  # Preview
                    'estado': 'OK' if campos['autorizacion'] else 'SIN_AUTORIZACION'
                })
                
                print(f"✓ ({len(texto_plano)} caracteres)")
            
            return resultados
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return [{
                'archivo': nombre,
                'pagina': 0,
                'autorizacion': None,
                'ruc': None,
                'numero_factura': None,
                'total': None,
                'estado': 'ERROR',
                'error': str(e)
            }]

# USO BÁSICO
if __name__ == "__main__":
    inicio = time.time()
    # 1. Inicializar (una sola vez)
    procesador = ProcesadorEasyOCR()
    
    # 2. Procesar archivos (ejemplo con uno, luego lo adaptas para 1500)
    # pdf_test = "files/Ceci by iScanner.pdf"
    
    resultados = procesador.procesar_pdf(pdf_path)
    df = pd.DataFrame(resultados)
    
    # 3. Ver resultado
    print("\n" + "="*60)
    print("RESULTADO:")
    print(df[['archivo', 'pagina', 'autorizacion', 'ruc', 'total']])
    
    # 4. Guardar
    df.to_csv("resultado_easyocr.csv", index=False, encoding='utf-8')
    fin=time.time()
    segundos_totales=fin - inicio
    minutos = int(segundos_totales // 60)
    segundos = int(segundos_totales % 60)
    print("\n💾 Guardado en: resultado_easyocr.csv")
    print(f"\n⏱️ Tiempo total: {minutos} minutos y {segundos} segundos")
  


####    INICIO DE DEMO_PDF
import os
import sys
import time
from proccess_easy_ocr import ProcesadorEasyOCR     # ← la más probable
from read_xml_json.compare_xml_json import enriquecer_json_con_xml
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import main

# ================== CONFIGURACIÓN PDF ==================
# pdf_path = "files/25281-ALCANCE LIQ1412923-CALLE GARCIA JORGE.pdf"   # ← Cambia si es necesario
# pdf_path = "files/NAEL LAMAN LUZURIAGA 230.89.pdf"
# pdf_path = "files/JACQUELINE JOHNSON 2_compressed.pdf"
# pdf_path = "files/KAREN CASTRO 466.99.pdf"
pdf_path = "files/Ceci by iScanner.pdf"
# pdf_path = "files/Edison Molina_demo.pdf"

# ================== CONFIGURACIÓN JSON ==================
# json_path = "json_files/claves_25281-ALCANCE LIQ1412923-CALLE GARCIA JORGE.json"

if __name__ == "__main__":
    inicio = time.time()

    ruta_json = "json_files/claves_Ceci by iScanner.json"     # ← tu JSON del OCR
    ruta_xml = "comprobantes_xml/2503202601091442909700120011000000000365930867118.xml"  # ← el XML que descargaste
    procesador = ProcesadorEasyOCR()
    
    # Prueba con uno de tus PDFs
    lista_claves = procesador.procesar_pdf(pdf_path)
    
    print(f"\nSe encontraron {len(lista_claves)} claves de acceso")
    print(lista_claves)
    # main(json_path)     #   DESCARGA ARCHIVOS DE API
    print('*'*10)
    enriquecer_json_con_xml(ruta_json, ruta_xml)
    fin = time.time()
    minutos = int((fin - inicio) // 60)
    segundos = int((fin - inicio) % 60)
    print(f"\n⏱️ Tiempo total: {minutos} minutos y {segundos} segundos")