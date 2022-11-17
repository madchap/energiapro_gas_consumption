[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

# EnergiaPro gas consumption readings
This appdaemon will go fetch your gas data from EnergiaPro's customer portal, which you would find at https://www.holdigaz.ch/espace-client/views/view.login.php

This appdaemon's app only supports 1 gas installation.

> Warning: This code is based on Selenium and may break as the vendor is making changes to their website. If that's the case, please open up an issue. Otherwise, wait for an update, as for the foreseeable future, I will be using this appdaemon myself.

This code was written on x64 docker containers and runs in "production" on a Raspberry Pi 3b. I am not a developer, use at your own risk!

## High-level flow
- Login to customer portal and download xls file (using Selenium)
- Grab the excel file, and consume its last line
- POSTs the data to the following two new HA sensors:
  - `sensor.energiapro_gas_daily` (m3 of gas consumed in the day)
  - `sensor.energiapro_gas_total` (actual "relevé" in m3 on your installation)

There seems to be 2 postings a day to the portal. If you fetch the number somewhere in the middle of the afternoon, you'd have a certain number. If you read the next morning (for the previous day), the number will have been updated and the previous number overwritten.

# Energiapro pre-requisite
- Your gas installation is already equipped with EnergiaPro's LoraWan equipement.
- You already possess regular login credentials to EnergiaPro's customer portal and can see that the daily data is available there, also available as the XLS download.

If you are not equipped with the LoraWan stuff, you should be able to contact EnergiaPro and request its installation and configuration at no charge.

## AppDaemon's python and system packages pre-requisites
Make sure you have the following python packages installed:
- xlrd
- pandas
- requests
- selenium

You will need `chromium-chromedriver` system package installed as well for selenium to be able to work with the default settings, or `geckodriver` if you choose firefox.

You may also have to have support for `xvfb` on your underlying O/S.

## Configuration
### secrets.yaml
You will need the following in your secrets.yaml file

```
energiapro_email: <YOUR_EMAIL>
energiapro_password: <YOUR_PASSWORD>
energiapro_installation_number: "<YOUR_INSTALLATION_NUMBER>"
energiapro_bearer_token: <HA_LONG_LIVE_TOKEN>
```

> Don't forget to put your installation number between double quotes to avoid yaml truncating it.

### apps.yaml
Define your app like the following:

```
energiapro_gas_consumption:
  module: energiapro_gas
  class: EnergiaproGasConsumption
  energiapro_email: !secret energiapro_email
  energiapro_password: !secret energiapro_password
  energiapro_bearer_token: !secret energiapro_bearer_token
  energiapro_installation_number: !secret energiapro_installation_number
  # browser: firefox  # optional, defaults to chrome
  # ha_url: http://localhost:8123  # optional, in case hassplugin ha_url undefined
```

## Manually trigger the app
The app registers an endpoint at `energiapro_gas_consumption`. If you want to trigger a run manually, you can call that endpoint. Example:

```
$ curl -XPOST -i -H "Content-Type: application/json"  http://<YOUR_APPDAEMON_IP>:<YOUR_APPDAEMON_PORT>/api/appdaemon/energiapro_gas_consumption -d '{"action": "Call of Duty"}'
```

## Load historical data

#TODO

# Troubleshhoting
## Preferred driver
`chromedriver` is the preferred web driver (and the default, unless you override it), given the site uses WebGL and that Firefox support through `geckodriver` causes issues in many instances.

## Geckodriver not found
If you have chosen to run with Firefox and not Chrome, you may see this message.

```
FileNotFoundError: [Errno 2] No such file or directory: 'geckodriver'
Message: 'geckodriver' executable needs to be in PATH
```
If so, please download https://github.com/mozilla/geckodriver/releases and put in /usr/bin or somewhere in PATH

## Firefox not installed

```
Message: Expected browser binary location, but unable to find binary in default location, no 'moz:firefoxOptions.binary' capability provided, and no binary flag set on the command line
```

Install Firefox

## No error, but no data either
- Make sure you've configured your installation number within double quotes and that it is the right number.

# TODO:
- check not reloading same date several times
- how to backdate for previous day? (e.g. come up with good SQL probably)