from selenium.webdriver.common.action_chains import ActionChains

import time, random
driver = None

def click_con_movimiento(driver, elemento, pause_min=0.5, pause_max=1.5):
    actions = ActionChains(driver)
    
    # Mover mouse al elemento con pausa aleatoria
    actions.move_to_element(elemento)
    actions.pause(random.uniform(pause_min, pause_max))
    
    # Click con pequeña pausa post-click
    actions.click(elemento)
    actions.pause(random.uniform(0.2, 0.5))
    
    actions.perform()
    time.sleep(random.uniform(0.5, 1.0))  # Pausa adicional después del click