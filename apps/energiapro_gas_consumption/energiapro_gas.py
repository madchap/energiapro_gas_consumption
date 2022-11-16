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


class EnergiaproGazConsumption(hassapi.Hass):
    global download_folder
    download_folder = tempfile.mkdtemp()

    async def my_callback(self, request, kwargs):
        data = await request.json()
        self.log(data)
        response = {"message": "Triggered!"}
        self.get_gaz_data()

        return response, 200

    def initialize(self):
        # register an API endpoint for manual triggering
        # call with something like
        # $ curl -XPOST -i -H "Content-Type: application/json" http://localhost:5050/api/appdaemon/energiapro_gaz_consumption -d '{"action": "Gazzz"}'
        self.register_endpoint(self.my_callback, "energiapro_gaz_consumption")
        # self.run_at_sunrise(self.get_gaz_data)

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
        self.log(df)

        self.post_to_entities(df)

    def get_downloaded_file_name(self):
        files = glob.glob(
            download_folder + f"/*{self.args['energiapro_installation_number']}*.xls"
        )
        # files = glob.glob(download_folder + "/*.xls")
        self.log(f"DEBUG: list of files: {str(files)}")
        last_file = max(files, key=os.path.getctime)
        self.log(f"DEBUG: last file: {last_file}")

        return last_file

    def cleanup_files(self):
        self.log("Cleaning up files")
        p = Path(download_folder)
        files_to_remove = list(
            p.glob(f"*{self.args['energiapro_installation_number']}*.xls")
        )
        for file in files_to_remove:
            file.unlink()

    def post_to_entities(self, df):
        if self.args["ha_url"]:
            # get HA's url from app's first, if configured/overriden by user
            ha_url = self.args["ha_url"]
        elif self.config["plugins"]["HASS"]["ha_url"]:
            # if not configured in app, get it from the hassplugin
            ha_url = self.config["plugins"]["HASS"]["ha_url"]
        else:
            self.log("No Home Assistant URL configured. Aborting")
            sys.exit(2)
        self.log(f"HA url is {ha_url}")

        def _post_daily_consumption():
            entity_url = f"{ha_url}/api/states/sensor.energiapro_gas_daily"
            self.log("POST'ing data to {}".format(entity_url))
            token = "Bearer {}".format(self.args["energiapro_bearer_token"])
            headers = {"Authorization": token, "Content-Type": "application/json"}

            last_daily_measure = df["QUANTITE EN M3"].iloc[-1]
            daily_payload = {
                "state": last_daily_measure,
                "attributes": {
                    "unit_of_measurement": "m³",
                    "device_class": "gas",
                    "state_class": "total_increasing",
                },
            }
            # self.log("payload {}".format(daily_payload))

            r = requests.post(entity_url, json=daily_payload, headers=headers)
            self.log("POST'ing status: {}".format(r.status_code))
            # self.log("Response content: {}".format(r.json()))

        def _post_total_consumption():
            entity_url = f"{ha_url}/api/states/sensor.energiapro_gas_total"
            self.log("POST'ing data to {}".format(entity_url))
            token = "Bearer {}".format(self.args["energiapro_bearer_token"])
            headers = {"Authorization": token, "Content-Type": "application/json"}

            total_measure = int(df["RELEVE"].iloc[-1])
            total_payload = {
                "state": total_measure,
                "attributes": {
                    "unit_of_measurement": "m³",
                    "device_class": "gas",
                    "state_class": "total_increasing",
                },
            }
            self.log("payload {}".format(total_payload))

            r = requests.post(entity_url, json=total_payload, headers=headers)
            self.log("POST'ing status: {}".format(r.status_code))

        _post_daily_consumption()
        _post_total_consumption()

    def get_gaz_data(self):
        base_url = "https://www.holdigaz.ch/espace-client"
        login_url = f"{base_url}/views/view.login.php"
        csv_base_export_link = f"{base_url}/views/view.statistiques.lpn.php?a="

        try:
            # virtual display
            # self.log("DEBUG: Starting virtual display")
            # display = Display(visible=0, size=(1440, 900))
            # display.start()

            self.log("DEBUG: Initiating browser")
            if self.args["browser"] == "firefox":
                # FF driver option - has issue with WebGL, won't work at times.
                options = webdriver.firefox.options.Options()
                options.add_argument("--headless")
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1440,900")
                options.set_preference("browser.download.dir", download_folder)
                options.set_preference("browser.download.folderList", 2)
                options.set_preference(
                    "browser.helperApps.neverAsk.saveToDisk",
                    "text/csv,application/vnd.ms-excel",
                )
                options.set_preference(
                    "browser.helperApps.neverAsk.openFile",
                    "text/csv,application/vnd.ms-excel",
                )
                options.set_preference(
                    "browser.download.manager.showWhenStarting", False
                )
                options.set_preference("browser.helperApps.alwaysAsk.force", False)
                driver = webdriver.Firefox(
                    options=options, service_log_path="/tmp/geckodriver.log"  # nosec
                )
            else:
                chrome_options = webdriver.chrome.options.Options()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--window-size=1440,900")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--no-sandbox")
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

            self.log("Waiting for portal to come up...")
            elem = WebDriverWait(driver, 30).until(
                EC.url_contains("view.espace-client.php")
            )

            self.log("Navigate to consumption page")
            # navigate to consumption page
            driver.get(
                f"{csv_base_export_link}{self.args['energiapro_installation_number']}"
            )

            # download file
            self.log("Identifying and waiting for download link")
            export_link = driver.find_element(By.ID, "exportLPN")
            # export_link = driver.find_element(By.LINK_TEXT, "Exporter tous les relevés")
            elem = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable(export_link)
            )
            self.log(f"Text of export_link: {export_link.text}")
            self.log("Downloading xls file")
            driver.find_element(By.ID, "exportLPN").click()
            time.sleep(2)
            self.log("Done downloading")
            filename = self.get_downloaded_file_name()
            self.log(f"File is {filename}. Converting to csv.")
            self.convert_xls_to_csv(filename)
            self.cleanup_files()
        except Exception as e:
            self.log(e)
        finally:
            driver.quit()
