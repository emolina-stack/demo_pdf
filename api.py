from dotenv import load_dotenv
import requests
import json
from pathlib import Path
import os
import time

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
        """Obtiene el Bearer token"""
        url = f"{BASE_URL}/auth/token"
        data = {"email": self.email, "password": self.password}

        print(f"🔑 Intentando login con email: {self.email}")

        response = requests.post(url, data=data)
        response.raise_for_status()

        self.token = response.json()["access_token"]
        print("✅ Token obtenido correctamente")
        return self.token

    def recuperar_comprobante(self, clave_acceso: str, async_mode: bool = True):
        """Recupera el comprobante"""
        url = f"{BASE_URL}/comprobantes/recuperar"
        
        headers = {"Authorization": f"Bearer {self.token}"}
        data = {
            "id_empresa": os.getenv("ID_EMPRESA"),
            "clave_acceso": clave_acceso,
            "api_key": self.api_key,
            "async": 1 if async_mode else 0
        }

        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        
        return response.json()

    def descargar_xml(self, clave_acceso: str, carpeta_destino: str = "comprobantes_xml", 
                     max_retries: int = 3) -> str:
        """
        Descarga el XML con reintentos automáticos
        """
        url = f"{BASE_URL}/comprobantes/xml"
        headers = {"Authorization": f"Bearer {self.token}"}
        params = {"clave_acceso": clave_acceso}

        Path(carpeta_destino).mkdir(parents=True, exist_ok=True)
        ruta = Path(carpeta_destino) / f"{clave_acceso}.xml"

        for intento in range(1, max_retries + 1):
            try:
                print(f"📥 Descargando XML (intento {intento}/{max_retries})...")
                
                response = requests.get(
                    url, 
                    headers=headers, 
                    params=params, 
                    timeout=30
                )
                
                response.raise_for_status()

                with open(ruta, "wb") as f:
                    f.write(response.content)

                print(f"✅ XML descargado correctamente: {ruta}")
                return str(ruta)

            except requests.exceptions.RequestException as e:
                print(f"   ⚠️ Intento {intento} fallido: {e}")
                
                if intento == max_retries:
                    print(f"❌ Falló después de {max_retries} intentos")
                    raise  # Re-lanza la excepción después del último intento
                
                # Backoff: espera más tiempo en cada intento
                espera = intento * 2  # 2s, 4s, 6s...
                print(f"   ⏳ Reintentando en {espera} segundos...")
                time.sleep(espera)

        raise Exception(f"No se pudo descargar el XML después de {max_retries} intentos")