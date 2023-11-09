import appdaemon.plugins.hass.hassapi as hassapi
from datetime import datetime, timedelta
import requests
import bcrypt
import json


class EnergiaproGasConsumption(hassapi.Hass):
    async def my_callback(self, request, kwargs):
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

    def post_to_entities(self, lpn_data):
        def _post_daily_consumption():
            entity_url = f"{ha_url}/api/states/sensor.energiapro_gas_daily"
            token = "Bearer {}".format(self.args["energiapro_bearer_token"])
            headers = {"Authorization": token, "Content-Type": "application/json"}

            record_date = datetime.strptime(lpn_data[0].get("date")[:-9], "%Y-%m-%d")
            last_daily_measure = lpn_data[0].get("quantite_m3")
            # if last measure is older than yesterday, zero it out
            # Remember we process 1 day old data anyways
            # naively account for time component with <2d
            if not (datetime.now() - record_date < timedelta(days=2)):
                self.log(f"Last measure is from {record_date}, so setting to 0.")
                last_daily_measure = 0

            daily_payload = {
                "state": last_daily_measure,
                "attributes": {
                    "unit_of_measurement": "m³",
                    "device_class": "gas",
                    "state_class": "total",
                },
            }
            requests.post(entity_url, json=daily_payload, headers=headers)
            self.log(f"POST'ed {last_daily_measure} to {entity_url}")

        def _post_daily_kwh_consumption():
            entity_url = f"{ha_url}/api/states/sensor.energiapro_gas_kwh_daily"
            token = "Bearer {}".format(self.args["energiapro_bearer_token"])
            headers = {"Authorization": token, "Content-Type": "application/json"}

            record_date = datetime.strptime(lpn_data[0].get("date")[:-9], "%Y-%m-%d")
            last_daily_measure = lpn_data[0].get("consommation_kw_h")
            # if last measure is older than yesterday, zero it out
            # Remember we process 1 day old data anyways
            # naively account for time component with <2d
            if not (datetime.now() - record_date < timedelta(days=2)):
                self.log(f"Last measure is from {record_date}, so setting to 0.")
                last_daily_measure = 0

            daily_payload = {
                "state": last_daily_measure,
                "attributes": {
                    "unit_of_measurement": "kwh",
                    "device_class": "gas",
                    "state_class": "total",
                },
            }
            requests.post(entity_url, json=daily_payload, headers=headers)
            self.log(f"POST'ed {last_daily_measure} to {entity_url}")

        def _post_total_consumption():
            entity_url = f"{ha_url}/api/states/sensor.energiapro_gas_total"
            token = "Bearer {}".format(self.args["energiapro_bearer_token"])
            headers = {"Authorization": token, "Content-Type": "application/json"}

            total_measure = lpn_data[0].get("index_m3")
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
            if self.args["ha_url"]:
                # get HA's url from app's first, if configured/overriden by user
                self.log("Using ha_url from app's configuration")
                ha_url = self.args["ha_url"]
            else:
                ha_url = self.config["plugins"]["HASS"]["ha_url"]
        except Exception as e:
            self.log(
                "No Home Assistant URL could be found. Please configure ha_url in the app's configuration. Aborting."
            )
            self.log(e)
            return

        _post_daily_consumption()
        _post_daily_kwh_consumption()
        _post_total_consumption()

    def get_gas_data(self, kwargs):
        hashpw = self.get_hashed_passwd
        token = self.get_token(hashpw)
        lpn_data = self.get_lpn_data(token)

        if len(lpn_data) == 1:
            self.post_to_entities(lpn_data)
        else:
            self.log("Got multiple lpn records, need only 1!")

    def get_hashed_passwd(self):
        salt = bcrypt.gensalt(rounds=11)
        hashpw = bcrypt.hashpw(self.args.get(b"energiapro_api_secret_seed"), salt)

        return hashpw

    def get_token(self, hashpw):
        base_url = self.args.get("energiapro_base_api_url")
        auth_ep = f"{base_url}/authenticate.php"

        payload = {
            "username": self.args.get("energiapro_api_username"),
            "secret_key": hashpw,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            r = requests.post(auth_ep, data=payload, headers=headers)
            if r.status_code == 200:
                data_without_bom = r.text.lstrip("\ufeff")
                json_data = json.loads(data_without_bom)
                if json_data["errorCode"] != 0:
                    raise Exception(
                        f"Backend returned non-zero error code: {json_data['error']} ({json_data['errorCode']})"
                    )
                token = json_data["token"]

                return token
        except Exception as e:
            self.log("Failure in generating token from secret hash!")

    def get_lpn_data(self, token):
        base_url = self.args.get("energiapro_base_api_url")
        api_ep = f"{base_url}/index.php"
        start_date = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        end_date = datetime.today().strftime("%Y-%m-%d")

        payload = {
            "client_id": self.args.get("energiapro_client_number"),
            "scope": "lpn-json",
            "num_inst": self.args.get("energiapro_installation_number"),
            "date_debut": start_date,
            "date_fin": end_date,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Bearer {token}",
        }

        try:
            r = requests.post(api_ep + "index.php", data=payload, headers=headers)
            if r.status_code == 200:
                data_without_bom = r.text.lstrip("\ufeff")
                json_data = json.loads(data_without_bom)
                if "errorCode" in json_data and json_data["errorCode"] != "0":
                    raise Exception(
                        f"Backend returned non-zero error code: {json_data['error']} ({json_data['errorCode']})"
                    )

                return json_data
        except Exception as e:
            self.log("Error getting lpn data" + e)
