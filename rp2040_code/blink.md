# blink.py
Control the LED on a RP2040 via BM Bus messages and receive ACK messages on the BM Bus + save logs to Spotter SD card.


## Example BM-side commands

### Blink:
```
bm pub device/led {"led":"blink","period_ms":400,"count":4,"color":"success"} text 0
```
You should see the following on the Spotter console:
``` 
1761460162.441 d47002cda85fa9d0, LED ACK: blink color=success on_ms=250 off_ms=250 count=4
```



### Solid on:
```
bm pub device/led {"led":"on","color":"white"} text 0
```
The light will stay on until you turn it off. You should see the following on the Spotter console:
```
1761460246.835 d47002cda85fa9d0, LED ACK: on color=white
```

### Off:
```
bm pub device/led {"led":"off"} text 0
```
You should see the following on the Spotter console:
```
1761460310.226 d47002cda85fa9d0, LED ACK: off
```