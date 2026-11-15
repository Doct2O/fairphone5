# How this script came to be?

This is side effect of me messing with the emulation on the external screen,
and figuring out when and why throttling kicks in.  
For the full story, see: README in the `hdmi-over-usb-c` folder relative to the root's repo.  
**TLDR:** the heavy emulation is not feasible on this HW, due to heat build up.

# What does it do?

When ran **as a root** it simply reads nodes in `/sys/class/thermal/thermal_zone*` and converts returned
values to the degree Celsius. Move the caret at the top, loop and repeat every two seconds and you got the script.

The output looks like this:

```
=== Fairphone 5 Live Temperatures ===
msm-skin-therm-usr   : 27°C
cpu-0-0-step         : 34°C
cpu-0-1-step         : 34°C
cpu-0-2-step         : 34°C
cpu-0-3-step         : 34°C
cpu-1-0-step         : 33°C
cpu-1-1-step         : 33°C
cpu-1-2-step         : 33°C
cpu-1-3-step         : 33°C
cpu-1-4-step         : 34°C
cpu-1-5-step         : 33°C
cpu-1-6-step         : 34°C
cpu-1-7-step         : 34°C
gpuss-0-step         : 33°C
gpuss-1-step         : 33°C
cpu-0-0-usr          : 34°C
cpu-0-1-usr          : 34°C
cpu-0-2-usr          : 35°C
cpu-0-3-usr          : 34°C
cpuss-0-usr          : 34°C
cpuss-1-usr          : 34°C
cpu-1-0-usr          : 34°C
cpu-1-1-usr          : 33°C
cpu-1-2-usr          : 34°C
cpu-1-3-usr          : 34°C
cpu-1-4-usr          : 34°C
cpu-1-5-usr          : 33°C
cpu-1-6-usr          : 34°C
cpu-1-7-usr          : 34°C
gpuss-0-usr          : 34°C
gpuss-1-usr          : 33°C
modem-skin-usr       : 31°C
sdm-skin-therm-usr   : 33°C
chg-skin-therm-usr   : 32°C
battery              : 28°C
```

# Small comment on the displayed values

Obviously the **cpu-\*** prefixed stuff are the CPUs values (duh), **gpuss-\*** are the GPU's cores (duhhh). 
**msm-**, **sdm-**, **chg-** prefixed are the thermistors soldered on the board.

There are duplicates with **\*-step** and **\*-usr**, the former is related to kernel's step_wise governor for low-level, hardware-enforced emergency throttling,
the latter uses the user_space governor, which passes temperature readings up to Android's userspace `thermal-engine` daemon to manage gradual clock/charging limits.  
The ones containing **skin** in the name usually represents the temperature of the chip's case, the other usually measures the temperature on the silicon die.

The sensors are grouped in whatever manner Qualcomm see them fit. Here is what AI has  to say about it
(take it with a grain of salt, didn't check, but seems reasonable, as it usually does in case of AI :) ):

| Sensor Prefix              | Physical Location / Core Mapping                                | Notes                                                                                                                                                                      |
| :------------------------- | :-------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`cpu-0-0` to `cpu-0-3`** | **Cluster 0 — Efficiency Cores (4x Cortex-A55)**                | 4 sensors distributed across the four A55 cores (`cpu0`–`cpu3`).                                                                                                           |
| **`cpu-1-0` to `cpu-1-7`** | **Cluster 1 — Performance + Prime Cores (4x Cortex-A78)**       | Larger performance cores have **2 sensors per core** (8 diodes total across `cpu4`–`cpu7`), with **`cpu-1-6` / `cpu-1-7`** sitting on the **2.7 GHz Prime core** (`cpu7`). |
| **`cpuss-0` / `cpuss-1`**  | **CPU Subsystem (CPUSS)**                                       | Shared L3 cache, DynamIQ cluster interconnect, and memory controller.                                                                                                      |
| **`gpuss-0` / `gpuss-1`**  | **GPU Subsystem (Adreno 643)**                                  | Two thermal diodes across the GPU block.                                                                                                                                   |
| **`modem-skin-usr`**       | **5G Modem / RF area**                                          | Virtual/board thermistor estimating outer skin temp near the cellular modem.                                                                                               |
| **`sdm-skin-therm-usr`**   | **SoC / Mainboard area**                                        | Board thermistor near the main QCM6490 package.                                                                                                                            |
| **`chg-skin-therm-usr`**   | **Charging IC / PMIC**                                          | Board thermistor near the power management / fast-charging circuitry.                                                                                                      |
| **`battery`**              | **Battery pack**                                                | Thermistor inside the replaceable 4,200 mAh battery.                                                                                                                       |