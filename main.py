from pathlib import Path
from api import PuntowAPI
import json
import os

def procesar_json_y_enviar_a_api(ruta_json: str):
    """Lee el JSON y descarga XML solo si no existe previamente"""
    
    # 1. Cargar el JSON
    with open(ruta_json, encoding='utf-8') as f:
        datos = json.load(f)
    
    # 2. Normalizar a lista de facturas
    lista_facturas = []
    
    if isinstance(datos, list):
        lista_facturas = datos
    elif isinstance(datos, dict):
        posibles_claves = ['facturas', 'data', 'comprobantes', 'items', 'autorizaciones', 'claves']
        for clave in posibles_claves:
            if clave in datos and isinstance(datos[clave], list):
                lista_facturas = datos[clave]
                break
    
    if not lista_facturas:
        print("❌ No hay facturas para procesar")
        return

    print(f"📋 Se encontraron {len(lista_facturas)} autorizaciones en el JSON\n")

    # Crear carpeta si no existe
    carpeta_xml = Path("comprobantes_xml")
    carpeta_xml.mkdir(parents=True, exist_ok=True)

    # 3. Conectar con la API
    api = PuntowAPI()
    api.obtener_token()

    # 4. Procesar cada factura
    for i, item in enumerate(lista_facturas, 1):
        if not isinstance(item, dict):
            continue

        clave = item.get("autorizacion_json")
        if not clave:
            print(f"⚠️ Item {i} sin clave de autorización")
            continue

        pdf_nombre = item.get("pdf_nombre", "Desconocido")
        print(f"[{i}/{len(lista_facturas)}] Procesando → {clave[:35]}...")

        # ==================== NUEVA LÓGICA: Verificar si ya existe ====================
        ruta_xml_existente = carpeta_xml / f"{clave}.xml"

        if ruta_xml_existente.exists():
            print(f"   ⏭️  XML ya existe → saltando descarga")
            item["estado"] = "ya_existia"
            item["ruta_xml"] = str(ruta_xml_existente)
            item["mensaje"] = "XML ya existía"
            continue
        # ============================================================================

        try:
            # Recuperar comprobante
            resultado = api.recuperar_comprobante(
                clave_acceso=clave,
                async_mode=True
            )
            
            # Descargar XML solo si no existía
            ruta_xml = api.descargar_xml(clave, carpeta_destino="comprobantes_xml")
            
            item["estado"] = "descargado"
            item["ruta_xml"] = ruta_xml
            item["mensaje"] = "Éxito"

            print(f"   ✅ Descargado correctamente\n")

        except Exception as e:
            item["estado"] = "error"
            item["error"] = str(e)
            print(f"   ❌ Error: {e}\n")

    # ==================== Resumen Final ====================
    total = len(lista_facturas)
    exitos = sum(1 for item in lista_facturas if item.get('estado') in ['descargado', 'ya_existia'])
    nuevos = sum(1 for item in lista_facturas if item.get('estado') == 'descargado')
    ya_existian = sum(1 for item in lista_facturas if item.get('estado') == 'ya_existia')
    errores = total - exitos

    print("="*70)
    print("✅ PROCESO FINALIZADO")
    print("="*70)
    print(f"Total procesados     : {total}")
    print(f"✅ Nuevos descargados : {nuevos}")
    print(f"⏭️  Ya existían       : {ya_existian}")
    print(f"❌ Errores            : {errores}")
    print("="*70)