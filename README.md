[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

# EnergiaPro gas consumption readings
This appdaemon will go fetch your gas data from EnergiaPro's customer portal, which you would find at https://www.holdigaz.ch/espace-client/views/view.login.php

This appdaemon's app only supports 1 gas installation (at least for now).

## High-level flow
- Login to customer portal and download xls file
- Grab the excel file, and consume its last line
- POSTs the data to the following two new HA sensors:
  - `sensor.energiapro_gas_daily` (m3 of gas consumed in the day)
  - `sensor.energiapro_gas_total` (actual "relevé" in m3 on your installation)

There seems to be 2 postings a day to the portal, but the numbers are usually available the day after. As far as I know, there is no "back-posting" the data in HA, unless we fiddle with the database, so the data will be skewed in time.

# Energiapro pre-requisite
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
- xlrd
- pandas
- requests

## Configuration
### secrets.yaml
You will need the following in your secrets.yaml file

```
energiapro_email: <YOUR_EMAIL>
energiapro_password: <YOUR_PASSWORD>
energiapro_installation_number: "<YOUR_INSTALLATION_NUMBER>"
energiapro_client_number: "<YOUR_CLIENT_NUMBER>"
energiapro_bearer_token: <HA_LONG_LIVE_TOKEN>
```

> Don't forget to put your installation number between double quotes to avoid yaml truncating it.

### apps.yaml
Define your app like the following:

```
energiapro_gas_consumption:
  module: energiapro_gas
  class: EnergiaproGasConsumption
  energiapro_base_url: https://www.holdigaz.ch/espace-client
  energiapro_email: !secret energiapro_email
  energiapro_password: !secret energiapro_password
  energiapro_bearer_token: !secret energiapro_bearer_token
  energiapro_installation_number: !secret energiapro_installation_number
  energiapro_client_number: !secret energiapro_client_number
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
