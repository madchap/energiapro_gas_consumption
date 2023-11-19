[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

This repo or its code author is not affiliated with EnergiaPro.

# HACS configuration
Make sure that you [have the AppDaemon discovery and tracking](https://hacs.xyz/docs/categories/appdaemon_apps) enabled for HACS.

# Breaking change, new way to get data
Over the past few months, EnergiaPro has introduced changes to their customer portal, the latest being CloudFlare Turnstile, an invisible reCaptcha mechanism to prevent automated bot to do... what I was doing :-/ Even though legit requests, this service detects bot activity and login will not work.

The main branch of this repository will become the `via-api` branch, and should therefore be the one showing up in HACS.

## EnergiaPro now has an (unadvertised) API
But all is not lost. While not advertised, there is an API available!

Until EnergiaPro officializes and socializes the API, you can reach out to them at clients@energiapro.ch to get more information for the API service.

## Energiapro pre-requisite
- Your gas installation is already equipped with EnergiaPro's LoraWan equipement.
- You already possess regular login credentials to EnergiaPro's customer portal and can see that the daily data is available there, also available as the XLS download.

If you are not equipped with the LoraWan stuff, you should be able to contact EnergiaPro and request its installation and configuration at no charge.

You will need to have the following information for configuration:
- Your installation number, which you can find in the customer portal or on your invoice.
  - As you configure this number for this app, the format looks like `123456.000`
- Your client number, which you can find on your invoice
  - The format is more like `123456`

## AppDaemon's python packages pre-requisites
Make sure you have the following python packages installed:
- (deprecated, can be removed for use with the API) xlrd
- (deprecated, can be removed for use with the API) pandas
- (deprecated, can be removed for use with the API) beautifulsoup4
- requests
- bcrypt
-

## Configuration
### secrets.yaml
You will need the following in your secrets.yaml file

```
(deprecated, can be removed for use with the API) energiapro_email: <YOUR_EMAIL>
(deprecated, can be removed for use with the API) energiapro_password: <YOUR_PASSWORD>
energiapro_installation_number: "<YOUR_INSTALLATION_NUMBER>"
energiapro_client_number: "<YOUR_CLIENT_NUMBER>"
energiapro_bearer_token: <HA_LONG_LIVE_TOKEN>
energiapro_api_base_url: "https://www.holdigaz.ch/espace-client-api/api/"
energiapro_api_username: "<API USER NUMBER>"
energiapro_api_secret_seed: "<SECRET COMMUNICATED TO YOU BY ENERGIAPRO>"
```

> Don't forget to put your installation number between double quotes to avoid yaml truncating it.

### apps.yaml
Define your app like the following. You can remove the deprecated secrets per the above too.

```
energiapro_gas_consumption:
  module: energiapro_gas
  class: EnergiaproGasConsumption
  energiapro_base_url: https://www.holdigaz.ch/espace-client
  # energiapro_email: !secret energiapro_email
  # energiapro_password: !secret energiapro_password
  energiapro_bearer_token: !secret energiapro_bearer_token
  energiapro_installation_number: !secret energiapro_installation_number
  energiapro_client_number: !secret energiapro_client_number
  energiapro_api_username: !secret energiapro_api_username
  energiapro_api_base_url: !secret energiapro_api_base_url
  energiapro_api_secret_seed: !secret energiapro_api_secret_seed
  # ha_url: http://localhost:8123  # optional, in case hassplugin ha_url undefined
```

The `energiapro_bearer_token` refers to a long-lived Home Assistant token, to post the result.

## Manually trigger the app
The app can register an endpoint at `energiapro_gas_consumption`, which was mainly used during development. It's been commented for "production".

If you want to trigger a run manually, uncomment the necessary line in the `initialize` method and you then can call that endpoint, such as:

```
$ curl -XPOST -i -H "Content-Type: application/json"  http://<YOUR_APPDAEMON_IP>:<YOUR_APPDAEMON_PORT>/api/appdaemon/energiapro_gas_consumption -d '{"action": "Call of Duty"}'
```

# Troubleshhoting
## No error, but no data either
- Make sure you've configured your installation number within double quotes and that it is the right number.

# TODO:
- how to backdate for previous day? (e.g. come up with good SQL probably)
- Load historical data
