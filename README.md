# Estimation of Energy Expenditure using Machine Learning and Wearable Sensors during Resistance Exercise

## Impedance Pneumography

### EIT Firmware edits

The initial commit includes the original firmware source code (<url>https://github.com/ABI-EIT/EIT-Device-Firmware</url>) which is modified slightly in later commits to fit the requirements of current study.

After the modifications and installation of the mentioned tool versions, the set_env.cmd is run which successfully found the paths. The generate_makefiles.bat is run successfully followed by make_debug.bat. The .hex file is located at _build/debug/firmware.debug.hex. Use the Teensy loader to upload it on the Teensy.

Arduino IDE
Install Arduino IDE and follow instructions on: <url>https://www.pjrc.com/teensy/td_download.html</url> for the Teensy board manager. The latest version is installed (1.59.0). The Arduio IDE Serial monitor can be utilized for initial checks 

#### Modifications:

<ul>
<li> Remove EIT loops for drive and sensing electrodes to replace with single pair of drive electrodes and single pair of sensing electrodes. </li>
<li> Change g_iSamples_per_cycle to 3, to correspond to an excitation frequency of 83kHz. This is the closest possible with integer samples per cycle to the frequency used by Physioflow Lab. </li>
<li> Corrected the g_iTarget_period_us to correspond correctly to the conversion from seconds to microseconds.</li>
</ul>

#### Pending:

<ul>
<li> Modify tests.h to correspond to eit.h changes </li>
</ul>
