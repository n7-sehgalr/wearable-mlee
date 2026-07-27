
void adc_collect_samples(uint32_t * sample_array, uint8_t samples);


// eit_iq_demodulation ( const_cast<&g_aiSamples[g_iSample_rubbish]>, g_iSamples_useful, g_iSamples_per_cycle);
float eit_iq_demodulation(uint32_t const * sample_array, uint8_t length, uint8_t samples_per_period, bool print_info = false)
{
    float s_cum=0;
    float i_cum=0;
    float q_cum=0;

    for ( unsigned int i = 0; 
          i < length;
          ++i)
    {
        float sample = sample_array[i] * ( 3.33f / 65536 ) ; // Covert ADC to Volts
        float omegat = PI * 2.0f * ( i / ( (float) samples_per_period) );
        s_cum += sample;
        i_cum += sample * cos( omegat ); // Could put known systematic phase offset in here
        q_cum += sample * sin( omegat ); // Could put known systematic phase offset in here
    }

    // Cheap ass FIR filter, (Where Ftarget is a factor of Fsampling)
    float s_mean = ( s_cum / length ) ;
    float i_mean = ( i_cum / length ) ;
    float q_mean = ( q_cum / length ) ;
 
    float magnitude = 2 * sqrt(pow(i_mean,2) + pow(q_mean,2));
    float phase = atan(q_mean/i_mean);

    // if ( print_info )
    // {
    //     Serial.print("\r\n s_mean : ");     Serial.print(s_mean,4);
    //     Serial.print(", i_mean : ");    Serial.print(i_mean,4);
    //     Serial.print(", q_mean : ");    Serial.print(q_mean,4);
    //     Serial.print(", magnitude : "); Serial.print(magnitude,4);
    //     Serial.print(", phase : ");     Serial.print(phase,4);
    //     Serial.print("\r\n");
    // }

    return magnitude;
}

// Map electrode index to physical pin
// When bMapElectrodesToLines is TRUE:
//  [17 18  19  ..... 32 ]
//  [1  2   3   ..... 16 ]
// When bMapElectrodesToLines is FALSE:
//  [2  4   6   ..... 32 ]
//  [1  3   5   ..... 31 ]
unsigned int transformElectrode(unsigned int electrode) 
{
    if (!g_bMapElectrodesToLines) return electrode;
    unsigned int transformed = (0xF & electrode) * 2;
    if ( electrode & 0x10 ) return transformed + 1;
    return transformed;
}

void collect_eit_frame()
    {
        // This function is called repeatedly by the main loop in main.cpp.
        // Muxes are enabled and drive electrodes are selected in setup() for efficiency.

        // --- Define Sensing Electrodes ---
        // We will measure two separate impedance channels.
        unsigned int senseAElectrode1 = 2, senseBElectrode1 = 3; // Channel 1
        unsigned int senseAElectrode2 = 4, senseBElectrode2 = 5; // Channel 2

        // --- Capture high-resolution timestamp ---
        // This is done at the start of the acquisition sequence for consistency.
        unsigned long currentTime = micros();

        // --- Measure Impedance Channel 1 ---
        // Connect the selected sensing pair for the first channel
        senseAMux.select((ADG732::Channel) transformElectrode(senseAElectrode1));
        senseBMux.select((ADG732::Channel) transformElectrode(senseBElectrode1));

        // Trigger and wait for ADC operation
        adc_collect_samples(const_cast<uint32_t * >(g_aiSamples), g_iSamples);

        // Calculate magnitude
        float magnitude1 = eit_iq_demodulation ( 
            const_cast<uint32_t const * >(&g_aiSamples[g_iSample_rubbish]), // Ignore "rubbish" samples. (impacted by mux settling time)
            g_iSamples_useful, 
            g_iSamples_per_cycle);

        // --- Measure Impedance Channel 2 ---
        // Connect the selected sensing pair for the second channel
        senseAMux.select((ADG732::Channel) transformElectrode(senseAElectrode2));
        senseBMux.select((ADG732::Channel) transformElectrode(senseBElectrode2));
        adc_collect_samples(const_cast<uint32_t * >(g_aiSamples), g_iSamples);
        float magnitude2 = eit_iq_demodulation ( 
            const_cast<uint32_t const * >(&g_aiSamples[g_iSample_rubbish]),
            g_iSamples_useful, 
            g_iSamples_per_cycle);

        // --- Read IMU Data ---
        // Get a new sensor event. The 'event' structure will be filled with orientation data.
        sensors_event_t event;
        bno.getEvent(&event);
        // Get linear acceleration (acceleration without gravity)
        imu::Vector<3> linearAccel = bno.getVector(Adafruit_BNO055::VECTOR_LINEARACCEL);

        // --- Combine and Send Data as CSV ---
        // Format: timestamp_us,impedance1,impedance2,orient_x,orient_y,orient_z,accel_x,accel_y,accel_z
        Serial.print(currentTime); Serial.print(",");
        Serial.print(magnitude1, 4); Serial.print(",");
        Serial.print(magnitude2, 4); Serial.print(",");
        Serial.print(event.orientation.x, 4); Serial.print(","); // Heading/Yaw
        Serial.print(event.orientation.y, 4); Serial.print(","); // Roll
        Serial.print(event.orientation.z, 4); Serial.print(","); // Pitch
        Serial.print(linearAccel.x(), 4); Serial.print(",");
        Serial.print(linearAccel.y(), 4); Serial.print(",");
        Serial.print(linearAccel.z(), 4);
        Serial.println();
        Serial.flush(); // Flush to ensure data is sent immediately
    }
