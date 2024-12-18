from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import time

def select_journey_type(driver,journey_type):
    if journey_type == 'ida':
        radio_button = driver.find_element(By.ID, 'journeyStationOrigin')
    elif journey_type == 'vuelta':
        radio_button = driver.find_element(By.ID, 'journeyStationDestin')
    else:
        raise ValueError("Invalid journey type. Use 'ida' or 'vuelta'.")
    driver.execute_script("arguments[0].click();", radio_button)

# Abre la página de Renfe
def renfe_enjoyer(hora_de_salida,ida_vuelta,fecha_input,mail,ctr,abono):
    # URL de la página de Renfe
    url = 'https://venta.renfe.com/vol/loginCEX.do?Idioma=es&Pais=ES'

    try:
        driver = webdriver.Chrome()
        driver.get(url)

        wait = WebDriverWait(driver, 100)
        wait.until(EC.element_to_be_clickable((By.ID, 'onetrust-reject-all-handler')))
        driver.find_element(By.ID, 'onetrust-reject-all-handler').click()
        correo= driver.find_element(By.ID, 'num_tarjeta')
        correo.send_keys(str(mail))

        passw= driver.find_element(By.ID, 'pass-login')
        passw.send_keys(str(ctr))

        wait.until(EC.element_to_be_clickable((By.ID, 'loginButtonId')))
        driver.find_element(By.ID, 'loginButtonId').click()
        wait.until(EC.url_contains('venta.renfe.com/vol/home.do'))

        driver.get('https://venta.renfe.com/vol/myPassesCard.do')
        time.sleep(2)

        str_abono='new'+str(abono)+'            '
        wait.until(EC.visibility_of_element_located((By.ID, str_abono)))
        button= driver.find_element(By.ID, str_abono)
        driver.execute_script("arguments[0].click();", button)

        # Espera hasta que el botón esté presente y sea clicable
        wait.until(EC.element_to_be_clickable((By.ID, 'journeyStationOrigin')))

        # Cambia 'ida' por 'vuelta' según sea necesario
        select_journey_type(driver,ida_vuelta)
        time.sleep(2)

        fecha = driver.find_element(By.ID, 'fecha1')
        fecha.clear()
        fecha.send_keys(fecha_input)

        # Busca los billetes
        buscar = driver.find_element(By.ID, 'submitSiguiente')
        driver.execute_script("arguments[0].click();", buscar)
        button_id=None

        # Bucle de recarga de la página
        while True:
            time.sleep(2)

            try:
                time.sleep(2)
                # Locate the row containing the target hour
                row = driver.find_element(By.XPATH, f"//td[@data-label='Salida' and contains(text(), '{hora_de_salida}')]/ancestor::tr")
                row_id = row.get_attribute("id")
                print(f"Found row with ID: {row_id}")

                # Construct the button ID using the row number
                button_id = f"continuar{row_id[3:]}"  # Extract number part from 'row{row_number}'

                # Try to find the button with the constructed ID
                button = driver.find_element(By.ID, button_id)
                print(f"Button with ID '{button_id}' exists.")

                driver.execute_script("arguments[0].click();", button)
                time.sleep(2)

                submit = driver.find_element(By.ID, 'submitSiguiente')
                driver.execute_script("arguments[0].click();", submit)
                try:
                    time.sleep(2)
                    modal= driver.find_element(By.ID, 'modalGeneric')
                    if modal.is_displayed():
                        print('No hay asientos recargando')
                        driver.refresh()
                except NoSuchElementException:
                    pass

                time.sleep(1)
                wait.until(EC.visibility_of_element_located(
                    (By.CLASS_NAME, 'paso4-enviar-billetes-passbook-boton-texto semibold')))
                break  # Exit the loop if the button is found

            except NoSuchElementException:
                print(f"Button with ID '{button_id}' does not exist. Reloading the page...")

                # Reload the page and wait for it to load
                driver.refresh()

        input('Presiona Enter para cerrar el navegador...')
        driver.quit()

    except Exception as e:
        print(e)
