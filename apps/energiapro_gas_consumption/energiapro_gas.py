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

        minutes = 20
        self.log(f"Will fetch gas data every {minutes} minutes")
        self.run_every(self.get_gas_data, datetime.now(), minutes * 60)

    def post_to_entities(self, lpn_data):
        def _post_daily_consumption(daily_m3):
            entity_url = f"{ha_url}/api/states/sensor.energiapro_gas_daily"
            token = "Bearer {}".format(self.args["energiapro_bearer_token"])
            headers = {"Authorization": token, "Content-Type": "application/json"}

            daily_payload = {
                "state": daily_m3,
                "attributes": {
                    "unit_of_measurement": "m³",
                    "device_class": "gas",
                    "state_class": "total",
                },
            }
            requests.post(entity_url, json=daily_payload, headers=headers)
            self.log(f"POST'ed {daily_m3} to {entity_url}")

        def _post_daily_kwh_consumption(daily_kwh):
            entity_url = f"{ha_url}/api/states/sensor.energiapro_gas_kwh_daily"
            token = "Bearer {}".format(self.args["energiapro_bearer_token"])
            headers = {"Authorization": token, "Content-Type": "application/json"}

            daily_payload = {
                "state": daily_kwh,
                "attributes": {
                    "unit_of_measurement": "kwh",
                    "device_class": "gas",
                    "state_class": "total",
                },
            }
            requests.post(entity_url, json=daily_payload, headers=headers)
            self.log(f"POST'ed {daily_kwh} to {entity_url}")

        def _post_total_consumption(index_total):
            entity_url = f"{ha_url}/api/states/sensor.energiapro_gas_total"
            token = "Bearer {}".format(self.args["energiapro_bearer_token"])
            headers = {"Authorization": token, "Content-Type": "application/json"}

            total_payload = {
                "state": index_total,
                "attributes": {
                    "unit_of_measurement": "m³",
                    "device_class": "gas",
                    "state_class": "total_increasing",
                },
            }
            r = requests.post(entity_url, json=total_payload, headers=headers)
            self.log(f"POST'ed {index_total} to {entity_url}")

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

        # There can be multiple data elements sent, but they may all come at once upon query.
        # add up daily measures, otherwise, will only take the last one.
        qm3 = sum(float(element["quantite_m3"]) for element in lpn_data)
        kwh = sum(float(element["consommation_kw_h"]) for element in lpn_data)
        total = max(float(element["index_m3"]) for element in lpn_data)
        _post_daily_consumption(qm3)
        _post_daily_kwh_consumption(kwh)
        _post_total_consumption(total)

    def get_gas_data(self, kwargs):
        def _post(ep, payload, headers):
            try:
                r = requests.post(ep, data=payload, headers=headers)
                if r.status_code == 200:
                    data_without_bom = r.text.lstrip("\ufeff")
                    json_data = json.loads(data_without_bom)
                    if "errorCode" in json_data and json_data["errorCode"] != "0":
                        error_message = (
                            f"{json_data['error']} ({json_data['errorCode']})"
                        )
                        # self.notifier(error_message)
                        raise Exception(
                            f"Backend returned non-zero error code: {error_message}"
                        )
                    return json_data
                else:
                    self.log(f"return code was {r.status_code} with {r.text}")
            except Exception as e:
                self.log(f"Response return code error")
                self.log(e)

        def get_hashed_passwd():
            try:
                salt = bcrypt.gensalt(rounds=11)
                seed = self.args.get("energiapro_api_secret_seed")
                hashpw = bcrypt.hashpw(seed.encode(), salt)
            except Exception as e:
                self.log(e)

            return hashpw

        def get_token(hashpw):
            auth_ep = f"{base_url}/authenticate.php"
            payload = {
                "username": self.args.get("energiapro_api_username"),
                "secret_key": hashpw,
            }
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            json_r = _post(auth_ep, payload, headers)

            return json_r["token"]

        def get_lpn_data(token):
            api_ep = f"{base_url}/index.php"
            # get data for yesterday only - there could be multiple elements in the array
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

            json_r = _post(api_ep, payload, headers)
            return json_r

        base_url = self.args["energiapro_api_base_url"]
        hashpw = get_hashed_passwd()
        token = get_token(hashpw)
        lpn_data = get_lpn_data(token)

        if lpn_data is None:
            # exception raised, no data
            return
        self.post_to_entities(lpn_data)

    def notifier(self, message):
        # friendly_name = self.get_state(kwargs['entity_name'], attribute='friendly_name')
        title = "EnergiaPro"

        # notify first found
        self.call_service("notify/notify", title=title, message=message)
        # notify front-end
        self.call_service(
            "persistent_notification/create",
            title="EnergiaPro",
            message=(f"{message}"),
        )
