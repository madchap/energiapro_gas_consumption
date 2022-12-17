import appdaemon.plugins.hass.hassapi as hassapi
from pathlib import Path
import pandas as pd
import tempfile
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import re


class EnergiaproGasConsumption(hassapi.Hass):
    download_folder = "not set"

    async def my_callback(self, request, kwargs):
        data = await request.json()
        self.log(data)
        response = {"message": "Triggered!"}
        self.get_gas_data(kwargs)

        return response, 200

    def initialize(self):
        # register an API endpoint for manual triggering
        # self.register_endpoint(self.my_callback, "energiapro_gas_consumption")

        # minutes = 60
        # self.log(f"Will fetch gas data every {minutes} minutes")
        # self.run_every(self.get_gas_data, datetime.now(), minutes * 60)
        mytime = "10:00:00"
        self.log(f"Will fetch gas data every day at {mytime}")
        self.run_daily(self.get_gas_data, mytime)
        # self.run_at_sunrise(self.get_gas_data)

    def convert_xls_to_csv(self, xls_filename):
        xls_data = pd.read_excel(xls_filename, engine="xlrd")
        csv_file = f"{download_folder}/energiapro_{self.args['energiapro_installation_number']}_data.csv"

        xls_data.to_csv(
            csv_file,
            index=None,
            header=True,
        )
        df = pd.DataFrame(pd.read_csv(csv_file))

        if len(df.columns) == 0:
            self.log(
                f"Didn't seem to get any data in the Excel file... count is {df.count()}."
            )
            self.log("Check your configuration (installation number).")

        self.post_to_entities(df)

    def cleanup_files(self):
        p = Path(download_folder)
        files_to_remove = list(p.glob("*"))
        for file in files_to_remove:
            file.unlink()

        p.rmdir()

    def post_to_entities(self, df):
        def _post_daily_consumption():
            entity_url = f"{ha_url}/api/states/sensor.energiapro_gas_daily"
            token = "Bearer {}".format(self.args["energiapro_bearer_token"])
            headers = {"Authorization": token, "Content-Type": "application/json"}

            last_daily_measure = df["QUANTITE EN M3"].iloc[-1]
            daily_payload = {
                "state": last_daily_measure,
                "attributes": {
                    "unit_of_measurement": "m³",
                    "device_class": "gas",
                    "state_class": "total",
                },
            }
            r = requests.post(entity_url, json=daily_payload, headers=headers)
            self.log(f"POST'ed {last_daily_measure} to {entity_url}")

        def _post_total_consumption():
            entity_url = f"{ha_url}/api/states/sensor.energiapro_gas_total"
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
            r = requests.post(entity_url, json=total_payload, headers=headers)
            self.log(f"POST'ed {total_measure} to {entity_url}")

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

        _post_daily_consumption()
        _post_total_consumption()

    def get_gas_data(self, kwargs):
        global download_folder
        base_url = self.args.get("energiapro_base_url")
        login_url = f"{base_url}/views/view.login.php"
        login_controller_link = f"{base_url}/controllers/controller.login.php"
        view_stats_link = f"{base_url}/views/view.statistiques.lpn.ajax.php"
        export_controller_link = f"{base_url}/controllers/controller.export.xls.php"

        def _get_xss_random_code(r, step):
            soup = BeautifulSoup(r.text, "html.parser")

            if step == "login":
                try:
                    xss_random_code = re.search(
                        r"xss-rand-login':\s+(\d+),", soup.prettify()
                    ).group(1)
                    return xss_random_code
                except Exception as e:
                    self.log("Could not get login XSS random code")
                    self.log(e)
            elif step == "export":
                try:
                    form = soup.find("form", {"class": "fileDownloadForm"})
                    xss_random_code = form.find("input", {"id": "XSS-rand"})["value"]
                    return xss_random_code
                except Exception as e:
                    self.log("Could not get export XSS random code")
                    self.log(e)

        try:
            login_payload = {
                "email": self.args["energiapro_email"],
                "password": self.args["energiapro_password"],
            }

            export_payload = {
                "instNum": self.args["energiapro_installation_number"],
                "adrAbo": self.args["energiapro_client_number"],
            }
        except Exception as config_e:
            self.log("There was a problem getting configuration values. Aborting.")
            return

        try:
            download_folder = tempfile.mkdtemp()
            with requests.Session() as s:
                lr = s.get(login_url)
                xss_random_code_login = _get_xss_random_code(lr, "login")
                # hidden_hash = soup.find("input", {'id': 'hash'})
                # self.log(f"hash is {hidden_hash}")
                login_payload["xss-rand-login"] = xss_random_code_login
                headers = {
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
                    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Accept": "*/*",
                    "X-Requested-With": "XMLHttpRequest",
                    "Sec-Ch-Ua-Platform": "Linux",
                    "Origin": "https://www.holdigaz.ch",
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Dest": "empty",
                    "Referer": "https://www.holdigaz.ch/espace-client/views/view.login.php",
                    "Accept-Encoding": "gzip, deflate",
                    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8,es;q=0.7,zu;q=0.6,de;q=0.5,it;q=0.4",
                    "Cookie": f"espace-client={s.cookies.get('espace-client')}",
                }

                r = s.post(login_controller_link, data=login_payload, headers=headers)
                local_filename = f"{download_folder}/energiapro_{self.args['energiapro_installation_number']}_data.xls"

                if (
                    r.status_code == 200 and r.text == "true"
                ):  # The controller 'true' resp is the real thing
                    self.log("Login successful")

                    headers["Sec-Fetch-Mode"] = "navigate"
                    headers["Sec-Fetch-Dest"] = "document"
                    headers[
                        "Referer"
                    ] = "https://www.holdigaz.ch/espace-client/views/view.espace-client.php"
                    dr = s.get(view_stats_link, headers=headers)
                    xss_random_code_export = _get_xss_random_code(dr, "export")
                    export_payload["XSS-rand"] = xss_random_code_export
                    with s.post(
                        export_controller_link,
                        data=export_payload,
                        stream=True,
                        headers=headers,
                    ) as dl:

                        dl.raise_for_status()
                        with open(local_filename, "wb") as f:
                            for c in dl.iter_content(chunk_size=8192):
                                f.write(c)
                        self.log("File downloaded")
                else:
                    self.log(
                        f"login failed with error code {r.status_code} and text as {r.text}"
                    )
                self.convert_xls_to_csv(local_filename)
        except Exception as e:
            self.log(e)
        finally:
            self.cleanup_files()
