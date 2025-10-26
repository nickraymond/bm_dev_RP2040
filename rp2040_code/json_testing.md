# `json_testing.py`
This script demonstrates sending and receiving JSON-formatted messages over BM Bus using an RP2040 microcontroller to emulate readings and then writting to a config file.

When you enter a command in the Spotter console, the RP2040 will receive the message and send an ACK message back on the BM Bus.


## 0. Special setup for writting files to memory
Circuit Python inclues some safety features when you are plugged into the device over USB. It prevents you code.py file from being able to write to files on the CIRCUITPY drive while you are connected over USB. To disable this feature, you need to create a file called `settings.toml` in the root of the CIRCUITPY drive with the following content:

You have a few options:

### A. Create `boot.py` in your main directory  with the following content:
Create a special boot.py file that will allow you to toggle between host-edit mode (CIRCUITPY visible to computer, but read-only to running code) and device-write mode (CIRCUITPY hidden from computer, but read-write to running code). 

To enter host-edit mode, simply jumper pin A3 to GND while resetting the RP2040. Otherwise it will boot into device-write mode by default. 
```
# boot.py — maintenance pin toggle for QT Py RP2040
import board, digitalio, storage, time

# Pick a safe pad (not SDA/SCL, not TX/RX, not NEOPIXEL)
MAINT_PIN = board.A3  # jumper A3 to GND while resetting for host-edit mode

key = digitalio.DigitalInOut(MAINT_PIN)
key.switch_to_input(pull=digitalio.Pull.UP)

# Simple debounce / settle
time.sleep(0.02)
pressed = not key.value  # LOW when jumpered to GND

if pressed:
    # Host-edit mode: CIRCUITPY visible to computer; keep FS read-only to running code
    storage.enable_usb_drive()
    # Do NOT remount RW for code while USB is visible.
else:
    # Device-write mode: hide USB; allow code to write files safely
    storage.disable_usb_drive()
    storage.remount("/", readonly=False)


```
### B. Unplug your USB cable from the RP2040 
If you want to test that this code is working you an simply unplug the USB cable after copying the code.py file to the CIRCUITPY drive. This will allow the code to write to files on the CIRCUITPY drive but you will not see the outputs from the MCU REPL until you plug the USB cable back in.

## 1. Test the LED

Enter the following commands into the Spotter Ebox console to control the LED on the RP2040:
``` 
bm pub device/led {"led":"on"} text 0
```

``` 
bm pub device/led {"led":"off"} text 0
```
You should see the following messages on the Spotter console:
```
1761514198.628 d47002cda85fa9d0, LED ACK: on white
1761514252.017 d47002cda85fa9d0, LED ACK: off
```

## 2. Test reading JSON config file
This will work regardless of the special setup for writting files to memory.

Enter the following command into the Spotter Ebox console to read the contents of config.json from the RP2040:
``` 
bm pub device/config/get {} text 0
```
You should see the following messages on the Spotter console:
```
1761514581.414 d47002cda85fa9d0, CFG GET SEEN
1761514581.437 d47002cda85fa9d0, CFG: {"sd_low_hz": 1, "sd_high_hz": 50, "imu_enabled": true, "tx_low_hz": 0.4, "tx_high_hz": 1}
```

This first message is confirmation that the RP2040 received the command, the second message is the contents of the config.json file.

## 3. Test writing JSON config file
Enter the following command into the Spotter Ebox console to write new contents to config.json on the RP2040:
``` 
bm pub device/config/set {"sd_high_hz":100,"tx_low_hz":0.9} text 0
```
You should see the following message on the Spotter console:
```
1761515045.398 d47002cda85fa9d0, CFG SET SEEN
1761515045.898 d47002cda85fa9d0, CFG SAVED: {"imu_enabled": true, "sd_high_hz": 100, "sd_low_hz": 1, "tx_high_hz": 1, "tx_low_hz": 0.9}
```