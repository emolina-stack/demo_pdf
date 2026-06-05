import json
import os
import sys
from pathlib import Path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from .read_xml import leer_xml_con_xmltodict

def normalizar_estructura_json(datos_ocr):
    """
    Normaliza cualquier estructura JSON a una lista de diccionarios
    """
    print(f"📋 Tipo original: {type(datos_ocr)}")
    
    # Caso 1: Ya es una lista de diccionarios
    if isinstance(datos_ocr, list):
        if all(isinstance(item, dict) for item in datos_ocr):
            print("✅ Estructura válida: lista de diccionarios")
            return datos_ocr
        else:
            # La lista contiene strings u otros tipos
            print("⚠️ La lista contiene elementos no-diccionario")
            return []
    
    # Caso 2: Es un diccionario
    elif isinstance(datos_ocr, dict):
        # Buscar posibles claves que contengan la lista de facturas
        posibles_claves = ['facturas', 'data', 'comprobantes', 'items', 'resultados']
        
        for clave in posibles_claves:
            if clave in datos_ocr and isinstance(datos_ocr[clave], list):
                print(f"✅ Encontrada lista en clave '{clave}'")
                return datos_ocr[clave]
        
        # Si no encontró una lista, asumir que el dict mismo es una factura
        if 'autorizacion' in datos_ocr or 'autorizacion_json' in datos_ocr:
            print("✅ El diccionario mismo es una factura")
            return [datos_ocr]
    
    # Caso 3: Es otra cosa (string, etc.)
    print(f"❌ Estructura no reconocida: {type(datos_ocr)}")
    return []


def enriquecer_json_con_xml(ruta_json_ocr: str, ruta_xml: str = None):
    """
    Compara y enriquece el JSON del OCR con los datos reales del XML.
    """
    # 1. Cargar JSON del OCR
    with open(ruta_json_ocr, encoding='utf-8') as f:
        datos_ocr = json.load(f)
    
    print(f"\n📄 JSON cargado: {ruta_json_ocr}")
    
    # 2. NORMALIZAR LA ESTRUCTURA (esto resuelve el error)
    lista_facturas = normalizar_estructura_json(datos_ocr)
    
    if not lista_facturas:
        print("❌ No se pudo normalizar la estructura del JSON")
        return None
    
    print(f"📊 Total facturas a procesar: {len(lista_facturas)}")
    
    # 3. Cargar XML
    if ruta_xml is None and lista_facturas:
        # Intentar obtener clave del primer elemento
        primer_item = lista_facturas[0]
        clave = primer_item.get("autorizacion") or primer_item.get("autorizacion_json")
        if clave:
            ruta_xml = f"../comprobantes_xml/{clave}.xml"
    
    if not ruta_xml or not Path(ruta_xml).exists():
        print(f"⚠️ No se encontró XML en: {ruta_xml}")
        # Buscar XMLs disponibles
        xmls = list(Path("comprobantes_xml").glob("*.xml"))
        if xmls:
            ruta_xml = str(xmls[0])
            print(f"📁 Usando XML alternativo: {ruta_xml}")
        else:
            print("❌ No hay XMLs disponibles")
            return None
    
    print(f"📄 XML cargado: {ruta_xml}")
    xml_data = leer_xml_con_xmltodict(ruta_xml)
    
    if not xml_data:
        print("❌ Error al leer el XML")
        return None
    
    # 4. Comparar y enriquecer
    resultado_desglosado = []
    
    for idx, item in enumerate(lista_facturas):
        if not isinstance(item, dict):
            print(f"⚠️ Item {idx} no es diccionario, saltando...")
            continue
        
        print(f"\n🔍 Procesando factura {idx + 1}/{len(lista_facturas)}")
        
        # Obtener clave de acceso (usando diferentes posibles nombres de campo)
        clave_ocr = item.get("autorizacion") or item.get("autorizacion_json") or item.get("clave_acceso")
        
        # Verificar si coincide con el XML
        clave_xml = xml_data.get("clave_acceso") or xml_data.get("numero_autorizacion")
        
        if clave_ocr == clave_xml:
            print("   ✅ Clave coincide")
            
            # Agregar metadata básica
            resultado_desglosado.append({
                "archivo": item.get("pdf_nombre", "desconocido"),
                "pagina": item.get("pagina", "N/A")
            })
            
            # COMPARACIÓN DE AUTORIZACIONES
            autorizacion_pdf = item.get("autorizacion_json") or item.get("autorizacion")
            autorizacion_xml = xml_data.get("numero_autorizacion")
            resultado_desglosado.append({
                "tipo": "autorizacion",
                "valor_ocr": autorizacion_pdf,
                "valor_xml": autorizacion_xml,
                "estado": "coincide" if str(autorizacion_pdf) == str(autorizacion_xml) else "no_coincide"
            })
            
            # COMPARACIÓN DE RUC
            ruc_pdf = item.get("ruc_json") or item.get("ruc")
            ruc_xml = xml_data.get("ruc_emisor")
            resultado_desglosado.append({
                "tipo": "ruc",
                "valor_ocr": ruc_pdf,
                "valor_xml": ruc_xml,
                "estado": "coincide" if str(ruc_pdf) == str(ruc_xml) else "no_coincide"
            })
            
            # COMPARACIÓN DE IDENTIFICACIÓN
            identificacion_pdf = item.get("identificacion_json") or item.get("identificacion")
            identificacion_xml = xml_data.get("identificacion_comprador")
            resultado_desglosado.append({
                "tipo": "identificacion",
                "valor_ocr": identificacion_pdf,
                "valor_xml": identificacion_xml,
                "estado": "coincide" if str(identificacion_pdf) == str(identificacion_xml) else "no_coincide"
            })
            
            # RAZÓN SOCIAL
            razon_social_pdf = item.get("razon_social_json") or item.get("razon_social")
            razon_social_xml = xml_data.get("razon_social_emisor")
            resultado_desglosado.append({
                "tipo": "razon_social",
                "valor_ocr": razon_social_pdf,
                "valor_xml": razon_social_xml,
                "estado": "coincide" if str(razon_social_pdf) == str(razon_social_xml) else "no_coincide"
            })
            
            # FECHA DE EMISIÓN
            fecha_pdf = item.get("fecha_emision") or item.get("fecha")
            fecha_xml = xml_data.get("fecha_emision")
            resultado_desglosado.append({
                "tipo": "fecha_emision",
                "valor_ocr": fecha_pdf,
                "valor_xml": fecha_xml,
                "estado": "coincide" if str(fecha_pdf) == str(fecha_xml) else "no_coincide"
            })
            
            # IMPORTE TOTAL
            total_pdf = item.get("total_json") or item.get("valor_total") or item.get("total")
            total_xml = xml_data.get("importe_total")
            resultado_desglosado.append({
                "tipo": "importe_total",
                "valor_ocr": total_pdf,
                "valor_xml": total_xml,
                "estado": "coincide" if str(total_pdf) == str(total_xml) else "no_coincide"
            })
            
        else:
            print(f"   ❌ Clave no coincide: OCR={clave_ocr} vs XML={clave_xml}")
            resultado_desglosado.append({
                "estado": "no_coincide_con_xml",
                "clave_ocr": clave_ocr,
                "clave_xml": clave_xml,
                "pdf_nombre": item.get("pdf_nombre", "desconocido")
            })
    
    # 5. Guardar JSON enriquecido
    carpeta_salida = Path("files_comparativo")
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    
    nombre_archivo = Path(ruta_json_ocr).stem + "_comparativo.json"
    ruta_salida = carpeta_salida / nombre_archivo
    
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(resultado_desglosado, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ JSON enriquecido guardado en: {ruta_salida}")
    
    # 6. Enviar a webhook (opcional)
    # try:
    #     from webhook_envio import enviar_a_webhook
    #     import os
    #     from dotenv import load_dotenv
    #     load_dotenv()
        
    #     print("📤 ENVIANDO RESULTADOS AL WEBHOOK...")
    #     # enviar_a_webhook(str(ruta_salida), os.getenv("WEBHOOK_URL"))
    #     print('✅ Resultados enviados al webhook')
    # except Exception as e:
    #     print(f"⚠️ Error enviando a webhook: {e}")
    
    return resultado_desglosado


# # ===================== USO =====================
# if __name__ == "__main__":
#     # Primero, debug para ver la estructura
#     ruta_json = "../json_files/clave_Ceci by iScanner.json"  # Cambia por tu ruta
#     # debug_json_estructura(ruta_json)
    
#     # Luego ejecutar la función principal
#     enriquecer_json_con_xml(ruta_json)