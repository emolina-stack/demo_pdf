from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc
from click_con_movimiento import click_con_movimiento
import time
import random

CHROME_MAJOR_VERSION = 148
BRAVE_PATH = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
SRI_URL = "https://srienlinea.sri.gob.ec/sri-en-linea/SriRucWeb/ConsultaRuc/Consultas/consultaRuc"


def consultar_sri_y_enriquecer(self, ruc: str, max_click_intentos: int = 3):
    driver = None
    try:
        # Inicializar navegador SOLO UNA VEZ
        print(f"   🌐 Iniciando navegador para RUC {ruc}")
        options = uc.ChromeOptions()
        options.binary_location = BRAVE_PATH
        options.add_argument("--start-maximized")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        driver = uc.Chrome(options=options, version_main=CHROME_MAJOR_VERSION, use_subprocess=True)
        wait = WebDriverWait(driver, 25)
        
        # Cargar página UNA SOLA VEZ
        driver.get(SRI_URL)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(random.uniform(2, 4))
        
        # Bucle de reintentos para la consulta
        for intento in range(1, max_click_intentos + 1):
            try:
                print(f"   🔄 Intento de consulta {intento}/{max_click_intentos} - RUC {ruc}")
                
                # Limpiar y volver a ingresar el RUC
                try:
                    campo = wait.until(EC.element_to_be_clickable((By.ID, "busquedaRucId")))
                    campo.clear()
                    campo.send_keys(ruc)
                    time.sleep(random.uniform(1, 2))
                except Exception as e:
                    print(f"   ⚠️ Error al ingresar RUC: {e}")
                    # Si falla, recargar página y reintentar
                    driver.refresh()
                    time.sleep(3)
                    campo = wait.until(EC.element_to_be_clickable((By.ID, "busquedaRucId")))
                    campo.clear()
                    campo.send_keys(ruc)
                    time.sleep(random.uniform(1, 2))
                
                # Hacer click en Consultar
                # boton = wait.until(EC.element_to_be_clickable((By.XPATH, "//button//span[contains(text(),'Consultar')]")))
                boton = driver.find_element(By.XPATH, "//button//span[contains(text(),'Consultar')]")
                click_con_movimiento(driver, boton)
                time.sleep(random.uniform(3, 5))
                
                # Verificar si hay mensaje de error
                xpath_msg = "//*[@id='sribody']/sri-root/div/div[2]/div/div/sri-consulta-ruc-web-app/div/sri-ruta-ruc/div[2]/div[1]/div[6]/div[2]/div/div[1]/div/div/p-messages/div/span"
                
                try:
                    msg_element = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, xpath_msg))
                    )
                    msg_text = msg_element.text
                    print(f'   ⚠️ Mensaje de error: {msg_text}')
                    
                    # Cerrar el mensaje si se puede
                    try:
                        wait.until(EC.element_to_be_clickable((By.ID, "busquedaRucId"))).click()
                        time.sleep(1)
                    except:
                        pass
                    
                    # Si es el último intento, retornar error
                    if intento == max_click_intentos:
                        return {
                            "sri_consultado": False,
                            "sri_error": msg_text,
                            "intentos_realizados": intento
                        }
                    
                    # Esperar antes del siguiente intento
                    espera = intento * 3
                    print(f"   ⏳ Esperando {espera}s antes de reintentar...")
                    time.sleep(espera)
                    continue
                    
                except TimeoutException:
                    # No hay mensaje de error, intentar extraer datos
                    print("   ✅ No hay mensaje de error, extrayendo datos...")
                
                # Intentar extraer datos
                try:
                    # Esperar a que aparezca la tabla de resultados
                    wait.until(EC.presence_of_element_located((By.TAG_NAME, "sri-mostrar-contribuyente")))
                    time.sleep(random.uniform(2, 3))
                    
                    # Extraer identificación
#//*[@id="sribody"]/sri-root/div/div[2]/div/div/sri-consulta-ruc-web-app/div/sri-ruta-ruc/div[2]/div[1]/sri-mostrar-contribuyente/div[1]/div[2]/div[2]/div                    
                    razon_social = wait.until(
                        EC.visibility_of_element_located((By.XPATH, "//*[@id='sribody']/sri-root/div/div[2]/div/div/sri-consulta-ruc-web-app/div/sri-ruta-ruc/div[2]/div[1]/sri-mostrar-contribuyente/div[1]/div[2]/div[2]/div"))
                    )
                    razon_social_sri = razon_social.text.strip()
                    print(f"   📇 Razón social: {razon_social_sri}")
                    
                    # Extraer actividad económica
                    actividad = wait.until(
                        EC.visibility_of_element_located((By.XPATH, "//*[@id='sribody']/sri-root/div/div[2]/div/div/sri-consulta-ruc-web-app/div/sri-ruta-ruc/div[2]/div[1]/sri-mostrar-contribuyente/div[4]/div/div[1]/div[2]/table/tbody/tr/td"))
                    )
                    actividad_sri = actividad.text.strip()
                    print(f"   💼 Actividad económica: {actividad_sri}")
                    
                    datos_sri = {
                        "sri_consultado": True,
                        "sri_razon_social": razon_social_sri,
                        "sri_actividad": actividad_sri,
                    }
                    
                    print(f"   ✅ SRI consultado correctamente para RUC {ruc}")
                    return datos_sri
                    
                except Exception as e:
                    print(f"   ❌ Error extrayendo datos: {e}")
                    
                    if intento == max_click_intentos:
                        return {
                            "sri_consultado": False,
                            "sri_error": f"Error extrayendo datos: {e}",
                            "intentos_realizados": intento
                        }
                    
                    # Esperar antes del siguiente intento
                    espera = intento * 4
                    print(f"   ⏳ Esperando {espera}s antes de reintentar...")
                    time.sleep(espera)
                    continue
                    
            except Exception as e:
                print(f"   ❌ Error en intento {intento}: {e}")
                
                if intento == max_click_intentos:
                    return {
                        "sri_consultado": False,
                        "sri_error": str(e),
                        "intentos_realizados": intento
                    }
                
                espera = intento * 3
                print(f"   ⏳ Esperando {espera}s antes de reintentar...")
                time.sleep(espera)
        
    except Exception as e:
        print(f"   ❌ Error fatal inicializando navegador: {e}")
        return {
            "sri_consultado": False,
            "sri_error": f"Error de navegador: {e}",
            "intentos_realizados": 0
        }
    finally:
        
        if driver:
            driver.quit()
        # pass


resultado = consultar_sri_y_enriquecer(None, "0992548983001")
print(f"\n📊 Resultado final: {resultado}")