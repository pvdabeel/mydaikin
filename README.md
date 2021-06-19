
# MyDaikin - OS X Menubar plugin

Displays information about your Daikin Emura home airco system. Allows you to control the airco units in your home.

![Imgur](https://i.imgur.com/VTb32Si.png)


**Update 2019.10.20:**
- [X] Enable mode setting: Dry, Fan, Cool, Heat or Auto

**Update 2019.08.11:**
- [X] Detects and shows Daikin airco units 
- [X] Shows outdoor temperature, and indoor temperature per unit
- [X] Control target temperature, fan speed, fan direction

Builds on Daikin API [library](https://github.com/ael-code/daikin-control)

## Installation instructions: 

1. Ensure you have [bitbar](https://github.com/matryer/bitbar/releases/latest) installed.
2. Ensure your bitbar plugins directory does not have a space in the path (A known bitbar bug)
3. Copy [mydaikin.15m.py](mydaikin.15m.py) to your bitbar plugins folder and chmod +x the file from your terminal in that folder
4. Run bitbar (version 1.9 or <2.0-beta9, xbar not yet supported)
