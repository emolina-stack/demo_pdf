from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import undetected_chromedriver as uc
from .click_con_movimiento import click_con_movimiento
import time
import random
import json
import os
import glob
from datetime import datetime

CHROME_MAJOR_VERSION = 148
BRAVE_PATH = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
SRI_URL = "https://srienlinea.sri.gob.ec/sri-en-linea/SriRucWeb/ConsultaRuc/Consultas/consultaRuc"

CARPETA_ENTRADA = "json_files"
CARPETA_PROCESADOS_OK = os.path.join("json_files/procesados", "OK")
CARPETA_PROCESADOS_ERROR = os.path.join("json_files/procesados", "ERROR")


# ── 1. Utilidades de carpetas ─────────────────────────────────────────────────

def crear_carpetas():
    for carpeta in [CARPETA_ENTRADA, CARPETA_PROCESADOS_OK, CARPETA_PROCESADOS_ERROR]:
        os.makedirs(carpeta, exist_ok=True)
    print("📁 Estructura de carpetas verificada.")


def obtener_jsons_pendientes() -> list:
    archivos = glob.glob(os.path.join(CARPETA_ENTRADA, "*.json"))
    print(f"📋 JSONs encontrados en '{CARPETA_ENTRADA}': {len(archivos)}")
    return archivos


def mover_a_procesados(ruta_json: str, data: dict, exitoso: bool):
    nombre_base = os.path.splitext(os.path.basename(ruta_json))[0]
    sufijo = "enriquecido" if exitoso else "error"
    nombre_salida = f"{nombre_base}_{sufijo}.json"
    subcarpeta = CARPETA_PROCESADOS_OK if exitoso else CARPETA_PROCESADOS_ERROR
    ruta_salida = os.path.join(subcarpeta, nombre_salida)

    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    os.remove(ruta_json)  # elimina de pendientes para no reprocesar
    print(f"   {'✅' if exitoso else '❌'} Movido a: {ruta_salida}")
    return ruta_salida


# ── 2. Consulta al SRI (responsabilidad única: un RUC) ───────────────────────

def consultar_sri_y_enriquecer(ruc: str, driver, wait, max_click_intentos: int = 3):
    """Consulta un RUC en el SRI. Recibe driver y wait ya inicializados."""

    for intento in range(1, max_click_intentos + 1):
        try:
            print(f"   🔄 Intento {intento}/{max_click_intentos} - RUC {ruc}")

            # Ingresar RUC
            try:
                campo = wait.until(EC.element_to_be_clickable((By.ID, "busquedaRucId")))
                campo.clear()
                campo.send_keys(ruc)
                time.sleep(random.uniform(1, 2))
            except Exception as e:
                print(f"   ⚠️ Error al ingresar RUC: {e}. Recargando página...")
                driver.refresh()
                time.sleep(3)
                campo = wait.until(EC.element_to_be_clickable((By.ID, "busquedaRucId")))
                campo.clear()
                campo.send_keys(ruc)
                time.sleep(random.uniform(1, 2))

            # Click en Consultar
            boton = driver.find_element(By.XPATH, "//button//span[contains(text(),'Consultar')]")
            click_con_movimiento(driver, boton)
            time.sleep(random.uniform(3, 5))

            # Verificar mensaje de error del SRI
            xpath_msg = "//*[@id='sribody']/sri-root/div/div[2]/div/div/sri-consulta-ruc-web-app/div/sri-ruta-ruc/div[2]/div[1]/div[6]/div[2]/div/div[1]/div/div/p-messages/div/span"
            try:
                msg_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, xpath_msg))
                )
                msg_text = msg_element.text
                print(f'   ⚠️ Mensaje de error SRI: {msg_text}')

                try:
                    wait.until(EC.element_to_be_clickable((By.ID, "busquedaRucId"))).click()
                    time.sleep(1)
                except:
                    pass

                if intento == max_click_intentos:
                    return {"sri_consultado": False, "sri_error": msg_text, "intentos_realizados": intento}

                time.sleep(intento * 3)
                continue

            except TimeoutException:
                print("   ✅ Sin error del SRI, extrayendo datos...")

            # Extraer datos
            try:
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "sri-mostrar-contribuyente")))
                time.sleep(random.uniform(2, 3))

                razon_social_sri = wait.until(
                    EC.visibility_of_element_located((By.XPATH, "//*[@id='sribody']/sri-root/div/div[2]/div/div/sri-consulta-ruc-web-app/div/sri-ruta-ruc/div[2]/div[1]/sri-mostrar-contribuyente/div[1]/div[2]/div[2]/div"))
                ).text.strip()

                actividad_sri = wait.until(
                    EC.visibility_of_element_located((By.XPATH, "//*[@id='sribody']/sri-root/div/div[2]/div/div/sri-consulta-ruc-web-app/div/sri-ruta-ruc/div[2]/div[1]/sri-mostrar-contribuyente/div[4]/div/div[1]/div[2]/table/tbody/tr/td"))
                ).text.strip()

                ruc_sri = wait.until(
                    EC.visibility_of_element_located((By.XPATH, "//*[@id='sribody']/sri-root/div/div[2]/div/div/sri-consulta-ruc-web-app/div/sri-ruta-ruc/div[2]/div[1]/sri-mostrar-contribuyente/div[1]/div[1]/div[2]/div/span"))
                ).text.strip()

                print(f"   ✅ RUC: {ruc_sri} | Razón social: {razon_social_sri}")
                return {
                    "ruc": ruc_sri,
                    "sri_razon_social": razon_social_sri,
                    "sri_actividad": actividad_sri,
                }

            except Exception as e:
                print(f"   ❌ Error extrayendo datos: {e}")
                if intento == max_click_intentos:
                    return {"sri_error": str(e), "intentos_realizados": intento}
                time.sleep(intento * 4)
                continue

        except Exception as e:
            print(f"   ❌ Error en intento {intento}: {e}")
            if intento == max_click_intentos:
                return {"sri_error": str(e), "intentos_realizados": intento}
            time.sleep(intento * 3)

    return {"sri_error": "Sin respuesta tras todos los intentos"}


# ── 3. Procesar un JSON individual ───────────────────────────────────────────

def procesar_json(ruta_json: str, driver, wait) -> tuple[dict, bool]:
    """Procesa un archivo JSON y retorna (data_enriquecida, exitoso)."""
    with open(ruta_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    facturas = data.get("facturas", [])
    print(f"   📄 Facturas: {len(facturas)}")

    rucs_unicos = list({f["ruc"] for f in facturas})
    print(f"   🔍 RUCs únicos: {rucs_unicos}")

    # Consultar cada RUC único
    resultados_por_ruc = {}
    for ruc in rucs_unicos:
        print(f"\n   🔎 Consultando RUC: {ruc}")
        resultado = consultar_sri_y_enriquecer(ruc, driver, wait)
        resultados_por_ruc[ruc] = resultado
        time.sleep(random.uniform(2, 4))

    # Enriquecer facturas
    for factura in facturas:
        datos_sri = resultados_por_ruc.get(factura["ruc"], {})
        factura.update(datos_sri)

    # Determinar éxito
    facturas_con_error = [f for f in facturas if "sri_error" in f]
    exitoso = len(facturas_con_error) == 0

    # Agregar metadata
    # data["proceso"] = {
    #     "fecha_ejecucion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    #     "estado": "OK" if exitoso else "ERROR",
    #     "facturas_procesadas": len(facturas),
    #     "facturas_con_error": len(facturas_con_error),
    #     "rucs_consultados": rucs_unicos
    # }

    return data, exitoso


# ── 4. Función principal: recorre toda la carpeta ────────────────────────────

def procesar_todos_los_json():
    crear_carpetas()

    archivos = obtener_jsons_pendientes()
    if not archivos:
        print("⚠️  No hay archivos pendientes por procesar.")
        return

    # Abrir navegador UNA sola vez para todos los archivos
    print("\n🌐 Iniciando navegador...")
    options = uc.ChromeOptions()
    options.binary_location = BRAVE_PATH
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = uc.Chrome(options=options, version_main=CHROME_MAJOR_VERSION, use_subprocess=True)
    wait = WebDriverWait(driver, 25)
    driver.get(SRI_URL)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(random.uniform(2, 4))

    resumen = {"ok": 0, "error": 0}

    try:
        for ruta_json in archivos:
            nombre = os.path.basename(ruta_json)
            print(f"\n{'='*60}")
            print(f"📂 Procesando: {nombre}")
            print(f"{'='*60}")

            try:
                data, exitoso = procesar_json(ruta_json, driver, wait)
                mover_a_procesados(ruta_json, data, exitoso)
                resumen["ok" if exitoso else "error"] += 1

            except Exception as e:
                print(f"   ❌ Error fatal en {nombre}: {e}")
                data = {
                    "archivo": nombre,
                    "proceso": {
                        "fecha_ejecucion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "estado": "ERROR",
                        "error_fatal": str(e)
                    }
                }
                mover_a_procesados(ruta_json, data, exitoso=False)
                resumen["error"] += 1

    finally:
        driver.quit()
        print("\n🔒 Navegador cerrado.")

    print(f"""
╔══════════════════════════════╗
║       RESUMEN FINAL          ║
╠══════════════════════════════╣
║  ✅ Procesados OK : {resumen['ok']:<9}║
║  ❌ Con errores   : {resumen['error']:<9}║
║  📦 Total         : {len(archivos):<9}║
╚══════════════════════════════╝
    """)


# ── Punto de entrada ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    procesar_todos_los_json()