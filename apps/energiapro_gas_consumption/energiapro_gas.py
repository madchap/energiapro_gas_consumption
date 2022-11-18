import appdaemon.plugins.hass.hassapi as hassapi
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.chrome.options import Options
import glob
import os, sys
from pathlib import Path
import pandas as pd
import tempfile
import time
import requests


class EnergiaproGasConsumption(hassapi.Hass):
    global download_folder
    download_folder = tempfile.mkdtemp()

    async def my_callback(self, request, kwargs):
        data = await request.json()
        self.log(data)
        response = {"message": "Triggered!"}
        self.get_gas_data()

        return response, 200

    def initialize(self):
        # register an API endpoint for manual triggering
        self.register_endpoint(self.my_callback, "energiapro_gas_consumption")
        self.run_at_sunrise(self.get_gas_data)

    def convert_xls_to_csv(self, xls_filename):
        xls_data = pd.read_excel(xls_filename, engine="xlrd")
        xls_data.to_csv(
            f"{download_folder}/energiapro_{self.args['energiapro_installation_number']}_data.csv",
            index=None,
            header=True,
        )
        df = pd.DataFrame(
            pd.read_csv(
                f"{download_folder}/energiapro_{self.args['energiapro_installation_number']}_data.csv"
            )
        )
        if len(df.columns) == 0:
            self.log(
                f"Didn't seem to get any data in the Excel file... count is {df.count()}."
            )
            self.log("Check your configuration (installation number).")

        self.post_to_entities(df)

    def get_downloaded_file_name(self):
        files = glob.glob(
            download_folder + f"/*{self.args['energiapro_installation_number']}*.xls"
        )
        last_file = max(files, key=os.path.getctime)

        return last_file

    def cleanup_files(self):
        self.log("Cleaning up files")
        p = Path(download_folder)
        files_to_remove = list(
            # p.glob(f"*{self.args['energiapro_installation_number']}*.xls")
            p.glob("*")
        )
        for file in files_to_remove:
            file.unlink()

        p.rmdir()

    def post_to_entities(self, df):
        try:
            ha_url = self.config["plugins"]["HASS"]["ha_url"]
            if self.args["ha_url"]:
                # get HA's url from app's first, if configured/overriden by user
                self.log("Using ha_url from app's configuration")
                ha_url = self.args["ha_url"]
        except Exception as e:
            self.log(
                "No Home Assistant URL could be found. Please configure ha_url in the app's configuration. Aborting."
            )
            self.log(e)
            return

        def _post_daily_consumption():
            entity_url = f"{ha_url}/api/states/sensor.energiapro_gas_daily"
            self.log("POST'ing data to {}".format(entity_url))
            token = "Bearer {}".format(self.args["energiapro_bearer_token"])
            headers = {"Authorization": token, "Content-Type": "application/json"}

            last_daily_measure = df["QUANTITE EN M3"].iloc[-1]
            self.log(f"Daily quantity {last_daily_measure}")
            daily_payload = {
                "state": last_daily_measure,
                "attributes": {
                    "unit_of_measurement": "m³",
                    "device_class": "gas",
                    "state_class": "total",
                },
            }

            r = requests.post(entity_url, json=daily_payload, headers=headers)
            self.log("POST'ing status: {}".format(r.status_code))

        def _post_total_consumption():
            entity_url = f"{ha_url}/api/states/sensor.energiapro_gas_total"
            self.log("POST'ing data to {}".format(entity_url))
            token = "Bearer {}".format(self.args["energiapro_bearer_token"])
            headers = {"Authorization": token, "Content-Type": "application/json"}

            total_measure = int(df["RELEVE"].iloc[-1])
            self.log(f"Total quantity {total_measure}")
            total_payload = {
                "state": total_measure,
                "attributes": {
                    "unit_of_measurement": "m³",
                    "device_class": "gas",
                    "state_class": "total_increasing",
                },
            }

            r = requests.post(entity_url, json=total_payload, headers=headers)
            self.log("POST'ing status: {}".format(r.status_code))

        _post_daily_consumption()
        _post_total_consumption()

    def get_gas_data(self):
        base_url = self.args.get("energiapro_base_url")
        login_url = f"{base_url}/views/view.login.php"
        csv_base_export_link = f"{base_url}/views/view.statistiques.lpn.php?a="

        try:
            chrome_options = webdriver.chrome.options.Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--window-size=1024,768")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            if self.args.get("energiapro_no_ssl_check") == "true":
                chrome_options.add_argument("--ignore-certificate-errors")
            prefs = {"download.default_directory": download_folder}
            chrome_options.add_experimental_option("prefs", prefs)
            driver = webdriver.Chrome(options=chrome_options)

            driver.implicitly_wait(3)
            self.log("Logging in")
            driver.get(login_url)
            email_el = driver.find_element(By.ID, "email")
            passwd_el = driver.find_element(By.ID, "password")
            email_el.clear()
            email_el.send_keys(self.args["energiapro_email"])
            passwd_el.clear()
            passwd_el.send_keys(self.args["energiapro_password"])
            driver.find_element(By.XPATH, '//button[text()="Login"]').click()

            # self.log("Waiting for portal to come up...")
            elem = WebDriverWait(driver, 30).until(
                EC.url_contains("view.espace-client.php")
            )

            # self.log("Navigate to consumption page")
            # navigate to consumption page
            driver.get(
                f"{csv_base_export_link}{self.args['energiapro_installation_number']}"
            )

            # download file
            # self.log("Identifying and waiting for download link")
            export_link = driver.find_element(By.ID, "exportLPN")
            # export_link = driver.find_element(By.LINK_TEXT, "Exporter tous les relevés")
            elem = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable(export_link)
            )
            self.log("Downloading xls file")
            driver.find_element(By.ID, "exportLPN").click()
            time.sleep(2)
            filename = self.get_downloaded_file_name()
            self.convert_xls_to_csv(filename)
            self.cleanup_files()
        except Exception as e:
            self.log(e)
        finally:
            driver.quit()
