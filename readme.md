# "hello_world" quick start guide
1. Update mote firmware
2. Install Circuit Python on your [RP2040 QTPY board](https://www.adafruit.com/product/4900)
3. Install `bm_serial.py` into the `lib` folder of your CIRCUITPY drive
4. Wire the mote to the RP2040 (as shown below)
5. Copy the `hello_world.py` to your CIRCUITPY drive and name it `code.py`
6. Send a command from you Spotter Ebox console, see messge in REPL

## 💾 Files you will need for the mote
Follow these instructions for flashing new firmware to mote 

[Updating the Dev Kit f**irmware**](https://www.notion.so/Updating-the-Dev-Kit-firmware-ea47c07ed03e46a5b46c731319168563?pvs=21). You can use the SD card to flash new firmware to the mote.

- This file is for the Bristlefin (large dev board)
[bm_mote_v1.0-serial_bridge-dbg.elf.dfu.bin](mote_code%2Fbm_mote_v1.0-serial_bridge-dbg.elf.dfu.bin)


- This file is for the BristleBack (small dev board) [serial_bridge_bristleback.elf.dfu.bin](mote_code%2Fserial_bridge_bristleback.elf.dfu.bin)

Load onto the SD card, then use command to push to mote

You’re going to use the `bridge dfu` command to update the Mote on the Dev Kit **from the Spotter** which has the file on the SD card.

The update command will take this format:

`bridge dfu <name of file> <target node id> 120000 force`

you should see the following when complete
``` 
92626t [BM_DFU] [INFO] Transfer complete!
92626t [BM_DFU] [INFO] Transitioning to state: update
92626t [BM_DFU] [INFO] File transferred, entering update phase.
92630t [BM_DFU] [INFO] Opening bm_mote_v1.0-serial_bridge-dbg.elf.dfu.bin
103491t [BRIDGE_SYS] [INFO] Neighbor 49cfe4d7cceb2771 added
105259t [BM_DFU] [INFO] Node 49cfe4d7cceb2771 update status: 1, 0
Update finished: 49cfe4d7cceb2771 success: 1 err:0
105260t [BM_DFU] [INFO] Transitioning to state: idle
```

## Wiring the RP2040 to the Mote
I am using an Adafruit RP2040 QTPY board for this example. The wiring is as follows:
![Wiring instructions.png](Wiring%20instructions.png)


## Send a message over BM Bus to the RP2040
Enter the following command into the Spotter Ebox console to send a message to the RP2040
``` 
bm pub device/test hello_world text 0
```

In the REPL of the RP2040 you should see the following message
```
code.py output:
Starting BM RX test…
Subscribing to topic: device/test
=== BM PUB RECEIVED ===
Node ID:    0x8C67D48B8E0A985E
Type:       0
Version:    0
Topic len:  11
Topic:      device/test
Data len:   11
Data (text): hello_world
Data (hex): 68656c6c6f5f776f726c64
=======================
```
## Next Steps
You have successfully sent and received a message over the BM Bus using the RP2040 and a Bristlemouth mote! You can now modify the code to send and receive different topics/messages as needed. 

# 🎉 Kuddos
Thanks to Sofar Firmware engineer Matthew Krause for helping update the bm_serial.py that makes this all possible! 