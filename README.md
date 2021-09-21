[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

# Poolstation for Home Assistant

This [Home Assistant](https://home-assistant.io/) custom component will integrate devices that connect to the poolstation domotic platform
for pool equipment like smart chlorinators of brands of the fluidra group like Idegis or Astral Pool.
It is very possible that this integration will also work with devices integrating in the Fluidra Connect platform with minimal changes but
i couldn't test it myself.

It allows you to read the chlorinator sensors like temperature, ph, salt concentration and current electrolysis production.
It also allows to read and write configuration values like target ph and target electrolysis production.
Lastly, it allows you to control the integrated relays of the chlorinator, which can be used to control the pool's pump, lights, cascade or really any device.

Pending features that are possible but I couldn't implement are Redox/ORP and free chlorine readings because I don't have those addons.
The chlorinator also have binary inputs but I didn't integrate them yet because I haven't had a need for them yet.