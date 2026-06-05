from pathlib import Path
from api import PuntowAPI
import json
import os

def procesar_json_y_enviar_a_api(ruta_json: str):
    """Lee el JSON (cualquier estructura) y envía todas las autorizaciones a la API"""
    
    # 1. Cargar el JSON
    with open(ruta_json, encoding='utf-8') as f:
        datos = json.load(f)
    
    print(f"📄 Tipo de dato cargado: {type(datos)}")
    
    # 2. Normalizar: convertir a lista de facturas
    lista_facturas = []
    
    if isinstance(datos, list):
        # Ya es una lista
        lista_facturas = datos
        print(f"✅ JSON es una lista con {len(lista_facturas)} elementos")
        
    elif isinstance(datos, dict):
        # Es un diccionario, buscar la lista
        posibles_claves = ['facturas', 'data', 'comprobantes', 'items', 'autorizaciones', 'claves']
        
        encontrado = False
        for clave in posibles_claves:
            if clave in datos and isinstance(datos[clave], list):
                lista_facturas = datos[clave]
                print(f"✅ Encontrada lista en clave '{clave}' con {len(lista_facturas)} elementos")
                encontrado = True
                break
        
        if not encontrado:
            # Si no encontró lista, mostrar ayuda
            print(f"❌ No se encontró una lista de facturas en el JSON")
            print(f"📋 Claves disponibles: {list(datos.keys())}")
            print(f"💡 Agrega una de estas claves: {posibles_claves}")
            print(f"💡 O asegúrate de que el JSON sea una lista directa.")
            return
    else:
        print(f"❌ Formato JSON no soportado: {type(datos)}")
        return
    
    if not lista_facturas:
        print("❌ No hay facturas para procesar")
        return
    
    print(f"\n📋 Se encontraron {len(lista_facturas)} autorizaciones en el JSON\n")
    
    # 3. Conectar con la API
    api = PuntowAPI()
    api.obtener_token()
    
    # 4. Procesar cada factura
    for i, item in enumerate(lista_facturas, 1):
        # Verificar que item sea diccionario
        if not isinstance(item, dict):
            print(f"⚠️ Item {i} no es diccionario (es {type(item)}), saltando...")
            continue
        
        clave = item.get("autorizacion_json")
        
        if not clave:
            print(f"⚠️ Item {i} no tiene 'autorizacion_json', saltando...")
            print(f"   Claves disponibles: {list(item.keys())}")
            continue
            
        pdf_nombre = item.get("pdf_nombre", "Desconocido")
        
        print(f"[{i}/{len(lista_facturas)}] Procesando → {clave[:30]}... (de {pdf_nombre})")
        
        try:
            # 5. Recuperar el comprobante
            resultado = api.recuperar_comprobante(
                clave_acceso=clave,
                async_mode=True
            )
            
            # 6. Descargar el XML
            ruta_xml = api.descargar_xml(clave, carpeta_destino="comprobantes_xml")
            
            # Guardar resultado
            item["estado"] = "descargado"
            item["ruta_xml"] = ruta_xml
            item["mensaje"] = "Éxito"
            
            print(f"   ✅ Descargado correctamente\n")
            
        except Exception as e:
            item["estado"] = "error"
            item["error"] = str(e)
            print(f"   ❌ Error: {e}\n")
    
    # # 7. Guardar JSON actualizado
    # output_path = ruta_json.replace('.json', '_procesado.json')
    # with open(output_path, 'w', encoding='utf-8') as f:
    #     json.dump(datos, f, ensure_ascii=False, indent=2)
    
    # print("="*70)
    # print(f"✅ PROCESO FINALIZADO")
    # print(f"📁 Resultados guardados en: {output_path}")
    print("="*70)
    
    # Mostrar resumen
    total = len(lista_facturas)
    exitos = sum(1 for item in lista_facturas if item.get('estado') == 'descargado')
    errores = total - exitos
    print(f"\n📊 Resumen: {exitos} exitosos, {errores} errores de {total} total")


# ====================== USO ======================
# if __name__ == "__main__":
#     json_path = "json_files/clave_3-1 (1).json"
#     procesar_json_y_enviar_a_api(json_path)

