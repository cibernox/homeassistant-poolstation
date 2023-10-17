[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

# Poolstation integration for Home Assistant

## What does it do?

This [Home Assistant](https://home-assistant.io/) custom component will integrate devices that connect to the poolstation domotic platform
for pool equipment like smart chlorinators of brands of the fluidra group like Idegis or Astral Pool.
It is very possible that this integration will also work with devices integrating in the Fluidra Connect platform with minimal changes but
i couldn't test it myself.

## Instalation with HACS
Once you have HACS installed in your home assistant, add `git@github.com:cibernox/homeassistant-poolstation.git` as a custom repository
for the category `Integrations`.

![HACS-add-poolstation](https://github.com/cibernox/homeassistant-poolstation/assets/265339/98ca21ee-5a01-454b-98b7-55c2c1fa4bf3)

After it's done (it might take a moment to refresh the list of integrations) you should be able to add this integration to your home assistant. 

## Current features

After connecting to the poolstation API with your email and password, it will create as many devices as pools you have in your account.

Each pool contains many entities:

- Water temperature (sensor: read only)
- Current PH level (sensor: read only)
- Salt concentration (sensor: read only)
- Electrolysis production (sensor: read only)
- Target PH level (number: read/write)
- Target electrolysis production (number: read/write)
- Relays (switch) (The number of relays depends on your model, mine has 4 relays: Pump, Light, Watering and Waterfall. The last three relays can be used for anything you want, those are just the default names, but a relay is a relay)
- Current ORP (sensor: read only)
- Target ORP (number: read/write)
- Current free chlorine (sensor: read only)
- Target free chlorine (number: read/write)
- Binary inputs (binary sensor: read only) (Depends on the model, mine has 4 which I don't use.)


## What can I do with it?

First, you don't have to use the web or ios/android app to turn on or off your pool, check the water temperature or adjust any parameter, you can do it from home assistant like the rest of your home. With some very nice UI if you want to spend some time:

![UI widget](https://user-images.githubusercontent.com/265339/132487373-dd1b9bdd-949e-44f2-b26d-27f126aa0681.jpg)

Also, you can create any kind of automations. Personally I prefer to schedule working times of the pump from home assistant with the scheduler card that from the poolstation platform.

You can configure notification when some value gets out of range. I turn my filtration on only when I have excess solar production from my solar panels to save energy.
