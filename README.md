# Estimation of Energy Expenditure using Machine Learning and Wearable Sensors during Resistance Exercise

## Impedance Pneumography

### EIT Firmware edits

The initial commit includes the original firmware source code (<url>https://github.com/ABI-EIT/EIT-Device-Firmware</url>) which is modified slightly in later commits to fit the requirements of current study.

After the modifications and installation of the mentioned tool versions, env.cmd is created with the following:
```powershell
@echo off

# Path to GNU Arm Embedded Toolchain
set ARMGCC_DIR=<Path>  # E.g. C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\11.2 2022.02

# Path to MinGW
set MinGW_DIR=<Path>  #E.g. C:\MinGW in my case

# Path to CMake
set CMAKE_DIR=<Path to CMake> #E.g. C:\Program Files\CMake

```

Now the set_env.cmd is run which successfully found the paths. The generate_makefiles.bat is run successfully followed by make_debug.bat. The .hex file is located at _build/debug/firmware.debug.hex. Use the Teensy loader to upload it on the Teensy.

Arduino IDE
Install Arduino IDE and follow instructions on: <url>https://www.pjrc.com/teensy/td_download.html</url> for the Teensy board manager. The latest version is installed (1.59.0). The Arduio IDE Serial monitor can be utilized for initial checks 

#### Modifications:

-  Remove EIT loops for drive and sensing electrodes to replace with single pair of drive electrodes and single pair of sensing electrodes. 
- Change g_iSamples_per_cycle to 3, to correspond to an excitation frequency of 83kHz. This is the closest possible with integer samples per cycle to the frequency used by Physioflow Lab.
- Corrected the g_iTarget_period_us to correspond correctly to the conversion from seconds to microseconds.
- Changed the gain to ~3.95 instead of 1000 in original by setting - g_iInputGainResistor1_ohms and g_iInputGainResistor2_ohms to 50,000
- Shift switch off/on of the muxes to outside the loop to avoid constant switching off/on each iteration of the loop. This adds a square wave component to the output if not removed.

#### Pending:

- Modify tests.h to correspond to eit.h changes

#### Recurring errors and resolution

- raise SerialException(msg.errno, "could not open port {}: {}".format(self._port, msg))
serial.serialutil.SerialException: [Errno 2] could not open port COM3: [Errno 2] No such file or directory: 'COM3'
    - USB may not be connected.
    - Port busy in another app
    - When using WSL, ports are not accessible by default. Follow - https://learn.microsoft.com/en-us/windows/wsl/connect-usb