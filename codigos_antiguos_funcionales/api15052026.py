from dotenv import load_dotenv
import requests
import json
from pathlib import Path
import os

load_dotenv()

BASE_URL = os.getenv("URL")

class PuntowAPI:
    def __init__(self):
        self.email = os.getenv("EMAIL")
        self.password = os.getenv("PASSWORD")
        self.id_empresa = int(os.getenv("ID_EMPRESA"))
        self.api_key = os.getenv("API_KEY")  

        if not all([self.email, self.password, self.api_key]):
            raise ValueError("❌ Faltan variables en el archivo .env (EMAIL, PASSWORD, ID_EMPRESA, API_KEY)")

    def obtener_token(self) -> str:
        """1. Obtiene el Bearer token con mejor manejo de errores"""
        url = f"{BASE_URL}/auth/token"
        
        data = {
            "email": self.email,
            "password": self.password
        }

        print(f"🔑 Intentando login con email: {self.email}")

        response = requests.post(url, data=data)   # form-urlencoded (funciona en la mayoría)

        # === DEBUG IMPORTANTE ===
        print(f"Status Code: {response.status_code}")
        print(f"Respuesta del servidor: {response.text}")

        if response.status_code == 422:
            print("❌ Error 422 → Probablemente email o contraseña incorrectos")
        elif response.status_code == 403:
            print("❌ Error 403 → La cuenta tiene 2FA activado (no se puede usar este endpoint)")

        response.raise_for_status()   # solo si todo está bien

        resultado = response.json()
        self.token = resultado["access_token"]
        print("✅ Token obtenido correctamente")
        return self.token

    def recuperar_comprobante(self, clave_acceso: str, async_mode: bool = True):
        """2. Recupera el comprobante (async o síncrono)"""
        url = f"{BASE_URL}/comprobantes/recuperar"
        
        headers = {
            "Authorization": f"Bearer {self.token}"
        }
        
        data = {
            "id_empresa": os.getenv("ID_EMPRESA"),
            "clave_acceso": clave_acceso,
            "api_key": self.api_key,
            "async": 1 if async_mode else 0
        }

        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        
        resultado = response.json()
        
        if async_mode:
            print("📥 Proceso encolado. URL de descarga:", resultado.get("descarga_xml_url"))
        else:
            print("✅ Comprobante recuperado en modo síncrono")
        
        return resultado

    def descargar_xml(self, clave_acceso: str, carpeta_destino: str = "xmls") -> str:
        """3. Descarga el XML del comprobante"""
        url = f"{BASE_URL}/comprobantes/xml"
        
        headers = {
            "Authorization": f"Bearer {self.token}"
        }
        
        params = {
            "clave_acceso": clave_acceso
        }

        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        # Crear carpeta si no existe
        Path(carpeta_destino).mkdir(exist_ok=True)
        
        nombre_archivo = f"{clave_acceso}.xml"
        ruta = Path(carpeta_destino) / nombre_archivo
        
        with open(ruta, "wb") as f:
            f.write(response.content)
        
        print(f"📄 XML guardado: {ruta}")
        return str(ruta)

