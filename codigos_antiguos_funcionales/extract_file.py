import re
from typing import Dict, List, Optional, Any

def extraer_campos(texto: str, detalles: List[Dict] = None) -> Dict[str, Any]:
    if not texto:
        return {
            "autorizacion": None, "ruc_emisor": None, "ruc_comprador": None,
            "numero_factura": None, "fecha_emision": None, "total": None,
            "subtotal": None, "iva": None, "razon_social": None, 
            "ambiente": None, "tipo_emision": None, "estado_extraccion": "SIN_TEXTO"
        }
    
    # Normalizar texto
    texto = texto.upper().strip()
    datos = {}
    
    # 1. NÚMERO DE AUTORIZACIÓN / CLAVE DE ACCESO (37-49 dígitos)
    # Prioriza los números más largos primero (49 dígitos es estándar actual SRI)
    patrones_auth = [
        r'(?:N[UÚ]MERO\s+DE\s+)?AUTORIZACI[OÓ]N\s*:?\s*(\d{37,49})',
        r'CLAVE\s+DE\s+ACCESO\s*:?\s*(\d{37,49})',
        r'C[OÓ]DIGO\s+DE\s+AUTORIZACI[OÓ]N\s*:?\s*(\d{37,49})',
        r'\b(\d{49})\b',  # Exactamente 49 dígitos (formato actual SRI)
        r'\b(\d{37})\b',  # 37 dígitos (formato antiguo)
    ]
    
    datos["autorizacion"] = None
    for patron in patrones_auth:
        match = re.search(patron, texto)
        if match:
            # Limpiar espacios que OCR a veces inserta
            auth = re.sub(r'\s+', '', match.group(1))
            if len(auth) >= 37:
                datos["autorizacion"] = auth
                break
    
    # 2. RUC EMISOR (generalmente aparece después de "R.U.C.:" arriba)
    # Busca el primer RUC válido (13 dígitos) - suele ser el del emisor
    rucs_encontrados = re.findall(r'(\d{13})\b', texto)
    datos["ruc_emisor"] = rucs_encontrados[0] if rucs_encontrados else None
    
    # RUC del comprador/cliente (a veces aparece como "RUC/CC:")
    match = re.search(r'(?:RUC/CC|C[ÉE]DULA|IDENTIFICACI[OÓ]N)[:\s]+(\d{10,13})', texto)
    datos["ruc_comprador"] = match.group(1) if match else None
    
    # 3. NÚMERO DE FACTURA (001-001-000000001 o similar)
    patrones_factura = [
        r'FACTURA\s*N[OÓ]?[:\s\.]*(\d{3}[-–]\d{3}[-–]\d{9,10})',
        r'N[OÚ]MERO[:\s]+(\d{3}[-–]\d{3}[-–]\d{9})',
        r'SECUENCIAL[:\s]+(\d{3}[-–]\d{3}[-–]\d{9})',
        r'(\d{3}[-–]\d{3}[-–]\d{9})',  # Fallback: cualquier secuencia válida
    ]
    
    datos["numero_factura"] = None
    for patron in patrones_factura:
        match = re.search(patron, texto)
        if match:
            # Normalizar guiones
            num = match.group(1).replace('–', '-').strip()
            datos["numero_factura"] = num
            break
    
    # 4. FECHAS (dd/mm/aaaa o dd-mm-aaaa)
    # Fecha de emisión (la más completa suele ser la principal)
    match = re.search(r'(\d{2}[/-]\d{2}[/-]\d{4})', texto)
    datos["fecha_emision"] = match.group(1).replace('-', '/') if match else None
    
    # Fecha y hora específica (para autorización)
    match = re.search(r'(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2}:\d{2})', texto)
    if match:
        datos["fecha_autorizacion"] = f"{match.group(1)} {match.group(2)}"
    else:
        datos["fecha_autorizacion"] = None
    
    # 5. VALORES MONETARIOS (Total, Subtotal, IVA)
    # Buscar patrones de dinero: $ 1,234.56 o 1.234,56 o 1234.56
    
    # Función auxiliar para limpiar montos
    def limpiar_monto(texto_monto: str) -> float:
        if not texto_monto:
            return None
        # Quitar símbolos de moneda y espacios
        limpio = re.sub(r'[$\s]', '', texto_monto)
        
        # Detectar formato (1,234.56 vs 1.234,56)
        if ',' in limpio and '.' in limpio:
            # Si el punto está después de la coma: 1,234.56 (formato inglés)
            if limpio.rfind('.') > limpio.rfind(','):
                limpio = limpio.replace(',', '')
            else:
                # Formato europeo/latino: 1.234,56
                limpio = limpio.replace('.', '').replace(',', '.')
        elif ',' in limpio:
            # Si hay coma y tiene 2 dígitos al final, es decimal europeo
            partes = limpio.split(',')
            if len(partes[-1]) == 2:
                limpio = limpio.replace('.', '').replace(',', '.')
            else:
                # Es separador de miles
                limpio = limpio.replace(',', '')
        
        try:
            return float(limpio)
        except:
            return None
    
    # Total (buscar palabras clave)
    patrones_total = [
        r'(?:TOTAL|VALOR\s+A\s+PAGAR|IMPORTE\s+TOTAL)[:\s]*[\$]?\s*([\d\.,]+(?:\s*\d{3})*[.,]\d{2})',
        r'TOTAL\s*USD[:\s]*([\d\.,]+)',
        r'TOTAL\s*A\s*PAGAR.*?([\d\.,]{3,}[.,]\d{2})'
    ]
    
    datos["total"] = None
    for patron in patrones_total:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            datos["total"] = limpiar_monto(match.group(1))
            break
    
    # Subtotal / Base imponible
    match = re.search(r'SUBTOTAL[:\s]*[\$]?\s*([\d\.,]+[.,]\d{2})', texto)
    datos["subtotal"] = limpiar_monto(match.group(1)) if match else None
    
    # IVA / Impuestos
    match = re.search(r'(?:IVA|TAX|VAT)[:\s]*[\$]?\s*([\d\.,]+[.,]\d{2})', texto)
    datos["iva"] = limpiar_monto(match.group(1)) if match else None
    
    # 6. RAZÓN SOCIAL / NOMBRE
    # Busca después de "Razón Social:", "Señor(es):", "Cliente:"
    patrones_nombre = [
        r'RAZ[OÓ]N\s+SOCIAL[:\s]+([A-ZÁÉÍÓÚÑ\s&]{5,60})',
        r'SE[NÑ]OR(?:ES)?[:\s]+([A-ZÁÉÍÓÚÑ\s]{5,50})',
        r'CLIENTE[:\s]+([A-ZÁÉÍÓÚÑ\s]{5,50})',
        r'DENOMINACI[OÓ]N[:\s]+([A-ZÁÉÍÓÚÑ\s]{5,60})'
    ]
    
    datos["razon_social"] = None
    for patron in patrones_nombre:
        match = re.search(patron, texto)
        if match:
            nombre = match.group(1).strip()
            # Limpiar si tiene palabras sueltas como "MATRIZ", "SUCURSAL"
            nombre = re.sub(r'\s+(MATRIZ|SUCURSAL|CIUDAD|DIRECCI[OÓ]N).*$', '', nombre, flags=re.I)
            if len(nombre) > 3:
                datos["razon_social"] = nombre[:100]  # Limitar longitud
                break
    
    # 7. METADATOS DEL DOCUMENTO
    # Ambiente (PRODUCCION/PRUEBAS)
    match = re.search(r'AMBIENTE[:\s]+(PRODUCCION|PRUEBAS?)', texto)
    datos["ambiente"] = match.group(1) if match else None
    
    # Tipo de emisión
    match = re.search(r'EMISI[OÓ]N[:\s]+(NORMAL|CONTINGENCIA)', texto)
    datos["tipo_emision"] = match.group(1) if match else None
    
    # 8. ESTADO DE LA EXTRACCIÓN
    campos_criticos = [datos["autorizacion"], datos["ruc_emisor"], datos["numero_factura"]]
    campos_encontrados = sum(1 for c in campos_criticos if c is not None)
    
    if campos_encontrados >= 3:
        datos["estado_extraccion"] = "COMPLETO"
    elif campos_encontrados >= 1:
        datos["estado_extraccion"] = "PARCIAL"
    else:
        datos["estado_extraccion"] = "INCOMPLETO"
    
    # Conteo de campos para métricas
    datos["campos_encontrados"] = campos_encontrados
    
    return datos

# Ejemplo de uso:
if __name__ == "__main__":
    texto_prueba = """
    R.U.C.: 0914429097001
    RAZÓN SOCIAL: FLORES MARIDUEÑA JESSICA DE LOURDES
    FACTURA No. 001-100-000000036
    
    NÚMERO DE AUTORIZACIÓN:
    2503202601091442909700120011000000000365930867118
    
    FECHA Y HORA DE AUTORIZACIÓN: 25/03/2026 13:10:15
    AMBIENTE: PRODUCCION
    EMISIÓN: NORMAL
    
    SUBTOTAL: $ 1.050,42
    IVA: $ 200,08
    TOTAL: $ 1.250,50
    """
    
    resultado = extraer_campos(texto_prueba)
    for k, v in resultado.items():
        print(f"{k}: {v}")
