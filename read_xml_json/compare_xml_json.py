import json
import os
import sys
import shutil
import time
import base64
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from .read_xml import leer_xml_con_xmltodict


def normalizar_estructura_json(datos_ocr):
    """
    Normaliza cualquier estructura JSON a una lista de diccionarios
    """
    print(f"📋 Tipo original: {type(datos_ocr)}")
    
    if isinstance(datos_ocr, list):
        if all(isinstance(item, dict) for item in datos_ocr):
            print("✅ Estructura válida: lista de diccionarios")
            return datos_ocr
        else:
            print("⚠️ La lista contiene elementos no-diccionario")
            return []
    
    elif isinstance(datos_ocr, dict):
        posibles_claves = ['facturas', 'data', 'comprobantes', 'items', 'resultados']
        for clave in posibles_claves:
            if clave in datos_ocr and isinstance(datos_ocr[clave], list):
                print(f"✅ Encontrada lista en clave '{clave}'")
                return datos_ocr[clave]
        
        if 'autorizacion' in datos_ocr or 'autorizacion_json' in datos_ocr:
            print("✅ El diccionario mismo es una factura")
            return [datos_ocr]
    
    print(f"❌ Estructura no reconocida: {type(datos_ocr)}")
    return []


def enriquecer_json_con_xml(ruta_json_ocr: str, ruta_xml: str = None):
    """
    Compara y enriquece el JSON del OCR con los datos reales del XML.
    Ahora busca el XML correcto para CADA factura.
    """
    # 1. Cargar JSON del OCR
    with open(ruta_json_ocr, encoding='utf-8') as f:
        datos_ocr = json.load(f)
    
    print(f"\n📄 JSON cargado: {ruta_json_ocr}")
    
    # 2. Normalizar estructura
    lista_facturas = normalizar_estructura_json(datos_ocr)
    
    if not lista_facturas:
        print("❌ No se pudo normalizar la estructura del JSON")
        return None
    
    print(f"📊 Total facturas a procesar: {len(lista_facturas)}")
    
    # 3. Preparar carpeta de XML procesados
    carpeta_xml_procesados = Path("comprobantes_xml/xml_procesados")
    carpeta_xml_procesados.mkdir(parents=True, exist_ok=True)

    resultado_desglosado = []

    # 4. Procesar cada factura con su propio XML
    for idx, item in enumerate(lista_facturas):
        if not isinstance(item, dict):
            continue

        print(f"\n🔍 Procesando factura {idx + 1}/{len(lista_facturas)}")

        # Obtener clave de esta factura
        clave_ocr = (
            item.get("autorizacion_json") or 
            item.get("autorizacion") or 
            item.get("clave_acceso")
        )

        if not clave_ocr:
            continue
            # print(f"   ⚠️ Factura sin clave de acceso")
            # resultado_desglosado.append({"estado": "sin_clave_ocr", "item": item})
            # continue

        # === BUSCAR XML CORRESPONDIENTE ===
        ruta_xml_actual = None
        carpeta_xml = Path("comprobantes_xml")

        for xml_file in carpeta_xml.glob("*.xml"):
            if clave_ocr in xml_file.name or clave_ocr in xml_file.read_text(encoding='utf-8', errors='ignore'):
                ruta_xml_actual = str(xml_file)
                break

        if not ruta_xml_actual:
            print(f"   ❌ No se encontró XML para clave: {clave_ocr[:40]}...")
            resultado_desglosado.append({
                "estado": "xml_no_encontrado",
                "clave_ocr": clave_ocr,
                "pdf_nombre": item.get("pdf_nombre", "desconocido")
            })
            continue

        # Leer XML y convertir a Base64
        try:
            with open(ruta_xml_actual, "rb") as f:
                xml_bytes = f.read()
                xml_base64 = base64.b64encode(xml_bytes).decode('utf-8')
            print(f"   🔄 XML convertido a Base64 ({len(xml_base64)} caracteres)")
        except Exception as e:
            print(f"   ❌ Error al convertir XML a Base64: {e}")
            xml_base64 = None

        # Leer XML de esta factura
        xml_data = leer_xml_con_xmltodict(ruta_xml_actual)
        if not xml_data:
            print("   ❌ Error al leer el XML")
            continue

        clave_xml = xml_data.get("clave_acceso") or xml_data.get("numero_autorizacion")

        print(f"   Comparando → OCR: {clave_ocr[:30]}... | XML: {clave_xml[:30]}...")

        # === COMPARACIONES ===
        if clave_ocr == clave_xml:
            print("   ✅ Clave coincide")
            pdf_nombre = ruta_json_ocr.replace("json_files/", "").replace(".json", ".pdf").replace("_comparativo", "").replace("clave_", "")
            resultado_desglosado.append({
                "pdf_nombre": pdf_nombre,
            })

            # Autorización
            resultado_desglosado.append({
                "autorizacion_json": clave_ocr,
                "autorizacion_xml": clave_xml,
                "estado": "coincide",
                "xml":xml_base64
            })

            # RUC
            ruc_pdf = item.get("ruc_json") or item.get("ruc")
            ruc_xml = xml_data.get("ruc_emisor")
            resultado_desglosado.append({
                "ruc_json": ruc_pdf,
                "ruc_xml": ruc_xml,
                "estado": "coincide" if str(ruc_pdf) == str(ruc_xml) else "no_coincide"
            })

            # COMPARACIÓN DE IDENTIFICACIÓN
            identificacion_pdf = item.get("identificacion_comprador_json")
            identificacion_xml = xml_data.get("identificacion_comprador")

            resultado_desglosado.append({
                # "identificacion_comprador_json": "",
                "identificacion_comprador_json": identificacion_pdf,
                # "identificacion_comprador_xml": "",
                "identificacion_comprador_xml": identificacion_xml,
                "estado": "coincide" if str(identificacion_pdf) == str(identificacion_xml) else "no_coincide"
            })
            
            # RAZÓN SOCIAL
            razon_social_pdf = item.get("razon_social_json") or item.get("razon_social")
            razon_social_xml = xml_data.get("razon_social_receptor")
            resultado_desglosado.append({
                "razon_social_json": razon_social_pdf,
                "razon_social_xml": razon_social_xml,
                "estado": "coincide" if str(razon_social_pdf) == str(razon_social_xml) else "no_coincide"
            })
            
            # FECHA DE EMISIÓN
            fecha_pdf = item.get("fecha_emision") or item.get("fecha")
            fecha_xml = xml_data.get("fecha_autorizacion")
            resultado_desglosado.append({
                "fecha_autorizacion_json": fecha_pdf,
                "fecha_autorizacion_xml": fecha_xml,
                "estado": "coincide" if str(fecha_pdf) == str(fecha_xml) else "no_coincide"
            })
            
            # IMPORTE TOTAL
            total_pdf_raw = item.get("total_json") or item.get("valor_total") or item.get("total")
            # importe_total_json = float(total_pdf_raw) if total_pdf_raw is not None or '' else None
            importe_total_json = float(total_pdf_raw) if total_pdf_raw not in (None, "", " ") else ''

            total_xml = xml_data.get("importe_total")
            importe_total_xml = float(total_xml)
            resultado_desglosado.append({
                "valor_total_json": importe_total_json,
                "valor_total_xml": importe_total_xml,
                "estado": "coincide" if str(importe_total_json) == str(importe_total_xml) else "no_coincide"
            })

        else:
            print(f"   ❌ Clave no coincide")
            resultado_desglosado.append({
                "estado": "no_coincide_con_xml",
                "clave_ocr": clave_ocr,
                "clave_xml": clave_xml,
                "pdf_nombre": item.get("pdf_nombre", "desconocido")
            })

        # === MOVER XML A PROCESADOS ===
        try:
            ruta_xml_path = Path(ruta_xml_actual)
            if ruta_xml_path.exists():
                destino = carpeta_xml_procesados / ruta_xml_path.name
                if destino.exists():
                    destino = carpeta_xml_procesados / f"{ruta_xml_path.stem}_dup_{int(time.time())}{ruta_xml_path.suffix}"
                shutil.move(str(ruta_xml_path), str(destino))
                print(f"   ✅ XML movido → {destino.name}")
        except Exception as e:
            print(f"   ⚠️ Error al mover XML: {e}")

    # 5. Guardar JSON enriquecido
    carpeta_salida = Path("files_comparativo")
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    
    nombre_archivo = Path(ruta_json_ocr).stem + "_comparativo.json"
    ruta_salida = carpeta_salida / nombre_archivo
    
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(resultado_desglosado, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ JSON comparativo guardado en: {ruta_salida}")

    enviado_correctamente = False
    try:
        from webhook_envio import enviar_a_webhook  
        
        #   ENVIO DE INFORMACION A WEBHOOK
        print("📤 Enviando JSON comparativo al webhook...")
        # enviado_correctamente = enviar_a_webhook(str(ruta_salida), os.getenv("WEBHOOK_URL")) #  ENVIO A WEBHOOK
        
        if enviado_correctamente:
            print("✅ JSON enviado correctamente al webhook")
        else:
            print("⚠️ No se pudo enviar al webhook")
            
    except Exception as e:
        print(f"❌ Error al enviar al webhook: {e}")
    # ===========================================================

    if enviado_correctamente:
        try:
            carpeta_destino = Path("files_comparativo/json_enviados")
            carpeta_destino.mkdir(parents=True, exist_ok=True)
            
            destino_final = carpeta_destino / nombre_archivo
            
            # Si ya existe, agregar sufijo para evitar sobrescribir
            if destino_final.exists():
                destino_final = carpeta_destino / f"{Path(nombre_archivo).stem}_{int(time.time())}{Path(nombre_archivo).suffix}"
            
            shutil.move(str(ruta_salida), str(destino_final))
            print(f"📦 JSON movido a carpeta enviados → {destino_final}")
            
        except Exception as e:
            print(f"⚠️ Error al mover el JSON: {e}")
    else:
        print("⚠️ No se movió el JSON porque no se envió correctamente al webhook")
    
    return resultado_desglosado