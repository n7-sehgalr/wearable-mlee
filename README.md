# Estimation of Energy Expenditure using Machine Learning and Wearable Sensors during Resistance Exercise

## Impedance Pneumography

### EIT Firmware edits

The initial commit includes the original firmware source code (<url>https://github.com/ABI-EIT/EIT-Device-Firmware</url>) which is modified slightly in later commits to fit the requirements of current study.

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
