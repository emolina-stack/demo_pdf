import requests
import json
from pathlib import Path

def enviar_a_webhook(json_data, webhook_url, timeout=30):
    try:
        # Si le pasas una ruta de archivo en vez de un dict
        if isinstance(json_data, str) and json_data.endswith('.json'):
            with open(json_data, 'r', encoding='utf-8') as f:
                payload = json.load(f)
        else:
            payload = json_data

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'ProcesadorFacturas/1.0'
        }

        response = requests.post(
            webhook_url,
            json=payload,           # ← Esta es la forma más fácil y recomendada
            headers=headers,
            timeout=timeout
        )

        # Verificar si fue exitoso
        if response.status_code in [200, 201, 202]:
            print(f"✅ Enviado correctamente al webhook | Status: {response.status_code}")
            return True
        else:
            print(f"⚠️ Error en webhook | Status: {response.status_code}")
            print(f"Respuesta: {response.text[:500]}")   # mostramos solo los primeros caracteres
            return False

    except requests.exceptions.Timeout:
        print("❌ Timeout: El webhook tardó demasiado en responder")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Error de conexión: No se pudo conectar con el webhook")
        return False
    except Exception as e:
        print(f"❌ Error inesperado al enviar webhook: {e}")
        return False

