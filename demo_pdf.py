import os
import sys
import shutil
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

# ================== IMPORTS ==================
from proccess_easy_ocr import ProcesadorFacturas
from read_xml_json.compare_xml_json import procesar_todos_los_comparativos
from main import procesar_json_y_enviar_a_api
from bot.actividad_economica import procesar_todos_los_json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ================== CONFIGURACIÓN ==================
pdf_folder = "files/"                    # Carpeta con los PDFs
carpeta_procesada = "documentos_procesados"
carpeta_no_procesada = "documentos_no_procesados"

# Crear carpetas
Path(carpeta_procesada).mkdir(parents=True, exist_ok=True)
Path(carpeta_no_procesada).mkdir(parents=True, exist_ok=True)

# Configuración de paralelismo
BATCH_SIZE = 10      # Procesar de 10 en 10
MAX_WORKERS = 3     # Número de workers simultáneos (ajusta según tu CPU/RAM)


def procesar_un_pdf(ruta_pdf: str):
    """Función que se ejecuta en cada Worker"""
    pdf_path = Path(ruta_pdf)
    inicio = time.time()
    
    try:
        procesador = ProcesadorFacturas()
        lista_claves = procesador.procesar_pdf(str(pdf_path))

        resultado = {
            "pdf": pdf_path.name,
            "estado": "error",
            "ruta_json": None,
            "tiempo": 0
        }

        if lista_claves and any(clave.get("autorizacion_json") for clave in lista_claves):
            # Éxito
            destino = Path(carpeta_procesada) / pdf_path.name
            shutil.move(str(pdf_path), str(destino))
            
            ruta_json = f"json_files/clave_{pdf_path.stem}.json"
            
            # Descargar XMLs APIIIS
            # procesar_json_y_enviar_a_api(ruta_json)  #  API

            resultado["estado"] = "éxito"
            resultado["ruta_json"] = ruta_json
            print(f"✅ {pdf_path.name} → Procesado correctamente")
        else:
            # Sin claves válidas
            destino = Path(carpeta_no_procesada) / pdf_path.name
            shutil.move(str(pdf_path), str(destino))
            print(f"⚠️  {pdf_path.name} → No se encontraron claves")
            
    except Exception as e:
        # Error
        destino = Path(carpeta_no_procesada) / pdf_path.name
        if pdf_path.exists():
            shutil.move(str(pdf_path), str(destino))
        print(f"❌ Error procesando {pdf_path.name}: {e}")
        resultado["error"] = str(e)

    resultado["tiempo"] = time.time() - inicio
    return resultado


def procesar_lote_pdfs(carpeta_pdfs: str):
    """Procesamiento principal por lotes con Workers"""
    pdf_files = list(Path(carpeta_pdfs).glob("*.pdf"))
    
    if not pdf_files:
        print(f"⚠️ No se encontraron PDFs en {carpeta_pdfs}")
        return

    print(f"📂 Encontrados {len(pdf_files)} PDFs")
    print(f"🚀 Iniciando procesamiento paralelo: {BATCH_SIZE} por lote | {MAX_WORKERS} workers\n")

    resultados_totales = []
    inicio_total = time.time()

    # Procesar por lotes
    for i in range(0, len(pdf_files), BATCH_SIZE):
        lote = pdf_files[i:i + BATCH_SIZE]
        print(f"\n📦 Procesando lote {i//BATCH_SIZE + 1}/{len(pdf_files)//BATCH_SIZE + 1} "
              f"({len(lote)} PDFs)")

        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_pdf = {executor.submit(procesar_un_pdf, str(pdf)): pdf for pdf in lote}
            
            for future in tqdm(as_completed(future_to_pdf), total=len(lote), desc="Procesando"):
                resultado = future.result()
                resultados_totales.append(resultado)

    # ================== RESUMEN FINAL ==================
    fin_total = time.time()
    exitos = sum(1 for r in resultados_totales if r["estado"] == "éxito")
    
    print("\n" + "="*80)
    print("🏁 PROCESAMIENTO FINALIZADO")
    print("="*80)
    print(f"Total PDFs procesados : {len(resultados_totales)}")
    print(f"Procesados con éxito  : {exitos}")
    print(f"Con errores           : {len(resultados_totales) - exitos}")
    duracion_segundos = fin_total - inicio_total

    # Conversión a horas, minutos y segundos
    horas = int(duracion_segundos // 3600)
    minutos = int((duracion_segundos % 3600) // 60)
    segundos = int(duracion_segundos % 60)
    # minutos_total = int((fin_total - inicio_total) // 60)
    # segundos_total = int((fin_total - inicio_total) % 60)
    # print(f"\n🎉 Lote completado en {minutos} min {segundos} seg")
    print(f"\n🎉 Lote completado en {horas}h {minutos:02d}m {segundos:02d}s")
    print("="*80)


if __name__ == "__main__":
    inicio_total = time.time()
    procesar_lote_pdfs(pdf_folder)
    print("*" * 80)
    procesar_todos_los_json()
    print("*" * 80)
    procesar_todos_los_comparativos()
    fin_total = time.time()
    duracion_segundos = fin_total - inicio_total
    horas = int(duracion_segundos // 3600)
    minutos = int((duracion_segundos % 3600) // 60)
    segundos = int(duracion_segundos % 60)

    print(f"\n🎉 Lote completado en {horas}h {minutos:02d}m {segundos:02d}s")