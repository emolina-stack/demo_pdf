import xmltodict
import json
from pathlib import Path
import xmltodict
import json
from pathlib import Path

def leer_xml_con_xmltodict(ruta_xml: str):
    """Versión corregida - maneja correctamente el CDATA"""
    with open(ruta_xml, encoding='utf-8') as f:
        xml_str = f.read()

    # Parsear el XML exterior
    data = xmltodict.parse(xml_str)

    # Extraer datos del envoltorio <autorizacion>
    autorizacion = data.get('autorizacion', {})

    # Extraer y parsear el CDATA (la factura real)
    comprobante_str = autorizacion.get('comprobante', '')
    if isinstance(comprobante_str, str):
        factura_dict = xmltodict.parse(comprobante_str)
    else:
        factura_dict = comprobante_str  # por si ya viene como dict

    factura = factura_dict.get('factura', {})

    info_tributaria = factura.get('infoTributaria', {})
    info_factura = factura.get('infoFactura', {})

    #   FORMATEAR FECHA
    fecha_autorizacion = autorizacion.get('fechaAutorizacion')
    def formatear_fecha_autorizacion(fecha_raw):
        from dateutil import parser
        if not fecha_raw:
            return ""
        
        try:
            dt = parser.parse(fecha_raw)                    # Parse automático
            return dt.strftime("%d/%m/%Y %H:%M:%S")
        except:
            return str(fecha_raw)[:19] if isinstance(fecha_raw, str) else ""
        
    # Datos principales
    info = {
        "numero_autorizacion": autorizacion.get('numeroAutorizacion'),
        "fecha_autorizacion": str(formatear_fecha_autorizacion(fecha_autorizacion)),
        
        "ruc_emisor": info_tributaria.get('ruc'),
        "identificacion_comprador":info_factura.get('identificacionComprador'),
        "importe_total": info_factura.get('importeTotal'),
        
        "razon_social_receptor": info_factura.get('razonSocialComprador'),        
    }

    return info

