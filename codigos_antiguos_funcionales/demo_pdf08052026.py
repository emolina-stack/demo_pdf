import os
import sys
import shutil
from pathlib import Path
from proccess_easy_ocr import ProcesadorFacturas     # ← la más probable
from read_xml_json.compare_xml_json import enriquecer_json_con_xml
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# from main import procesar_json_y_enviar_a_api
import time


# ================== CONFIGURACIÓN ==================
# Cambia la carpeta de PDFs a procesar por lotes
pdf_folder = "files/"  # ← Carpeta con los PDFs a procesar

# Carpetas de destino
carpeta_procesada = "documentos_procesados"
carpeta_no_procesada = "documentos_no_procesados"

# Crear carpetas si no existen
Path(carpeta_procesada).mkdir(parents=True, exist_ok=True)
Path(carpeta_no_procesada).mkdir(parents=True, exist_ok=True)

def procesar_lote_pdfs(carpeta_pdfs):
    """Procesa todos los PDFs en la carpeta por lotes"""
    procesador = ProcesadorFacturas()
    inicio_total = time.time()
    
    # Obtener lista de PDFs
    pdf_files = list(Path(carpeta_pdfs).glob("*.pdf"))
    
    if not pdf_files:
        print(f"⚠️  No se encontraron archivos PDF en {carpeta_pdfs}")
        return
    
    print(f"📂 Procesando {len(pdf_files)} PDFs en lote...")
    
    for pdf_path in pdf_files:
        print(f"\n🔄 Procesando: {pdf_path.name}")
        inicio_individual = time.time()
        
        try:
            # Procesar el PDF
            lista_claves = procesador.procesar_pdf(str(pdf_path))
            fin_individual = time.time()
            
            if lista_claves and any(clave.get("autorizacion_json") for clave in lista_claves):
                # Éxito: mover a procesada_alternativa
                destino = Path(carpeta_procesada) / pdf_path.name
                shutil.move(str(pdf_path), str(destino))
                print(f"✅ Procesado exitosamente → movido a {carpeta_procesada}")
                
                # Generar JSON de claves para este PDF
                ruta_json = f"json_files/clave_{pdf_path.stem}.json"
                
                # Descargar XMLs usando la API
                # procesar_json_y_enviar_a_api(ruta_json)#    USO DE API
                
                # Enriquecer con XML (asumiendo un XML por PDF, ajustar si es necesario)
                xml_files = list(Path("comprobantes_xml").glob("*.xml"))
                if xml_files:
                    ruta_xml = str(xml_files[-1])  # Último descargado, o implementar lógica mejor
                    enriquecer_json_con_xml(ruta_json, ruta_xml)
                
            else:
                # Fallo: mover a documentos_no_procesados
                destino = Path(carpeta_no_procesada) / pdf_path.name
                shutil.move(str(pdf_path), str(destino))
                print(f"❌ No se encontraron claves válidas → movido a {carpeta_no_procesada}")
            
            minutos = int((fin_individual - inicio_individual) // 60)
            segundos = int((fin_individual - inicio_individual) % 60)
            print(f"⏱️ Tiempo individual: {minutos} min {segundos} seg")
            
        except Exception as e:
            # Error: mover a no procesados
            destino = Path(carpeta_no_procesada) / pdf_path.name
            shutil.move(str(pdf_path), str(destino))
            print(f"❌ Error procesando {pdf_path.name}: {e} → movido a {carpeta_no_procesada}")
    
    fin_total = time.time()
    minutos_total = int((fin_total - inicio_total) // 60)
    segundos_total = int((fin_total - inicio_total) % 60)
    print(f"\n🎉 Lote completado en {minutos_total} min {segundos_total} seg")

if __name__ == "__main__":
    procesar_lote_pdfs(pdf_folder)

