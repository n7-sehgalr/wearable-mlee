
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


// This function is called at a fixed interval (e.g., 100Hz).
// It reads the IMU, combines it with the latest EIT data, and sends the packet.
void sample_and_send_data()
{
    // --- Capture high-resolution timestamp for the data packet ---
    unsigned long currentTime = micros();

    // --- Read IMU Data ---
    // struct from Adafruit holding timestamp, sensor id, sensor type and measurement values
    sensors_event_t event;
    //reads primary data from current sensor data and save in sensors_event_t struct called event
    // for BNO055, primary data is orientation, cannot get acceleration from here
    bno.getEvent(&event); 
    imu::Vector<3> linearAccel = bno.getVector(Adafruit_BNO055::VECTOR_LINEARACCEL);
    imu::Vector<3> gyro = bno.getVector(Adafruit_BNO055::VECTOR_GYROSCOPE);     // rad/s
    imu::Vector<3> gravity = bno.getVector(Adafruit_BNO055::VECTOR_GRAVITY);    // m/s²
    imu::Quaternion quat = bno.getQuat();                                        // unit quaternion

    // --- Combine and Send Data as CSV ---
    // Format: timestamp_us,orient_x,orient_y,orient_z,accel_x,accel_y,accel_z,gx,gy,gz,gravx,gravy,gravz,qw,qx,qy,qz
    Serial.print(currentTime); Serial.print(",");
    Serial.print(event.orientation.x, 4); Serial.print(","); // Heading/Yaw
    Serial.print(event.orientation.y, 4); Serial.print(","); // Roll
    Serial.print(event.orientation.z, 4); Serial.print(","); // Pitch
    Serial.print(linearAccel.x(), 4); Serial.print(",");
    Serial.print(linearAccel.y(), 4); Serial.print(",");
    Serial.print(linearAccel.z(), 4); Serial.print(",");
    Serial.print(gyro.x(), 4); Serial.print(",");
    Serial.print(gyro.y(), 4); Serial.print(",");
    Serial.print(gyro.z(), 4); Serial.print(",");
    Serial.print(gravity.x(), 4); Serial.print(",");
    Serial.print(gravity.y(), 4); Serial.print(",");
    Serial.print(gravity.z(), 4); Serial.print(",");
    Serial.print(quat.w(), 4); Serial.print(",");
    Serial.print(quat.x(), 4); Serial.print(",");
    Serial.print(quat.y(), 4); Serial.print(",");
    Serial.print(quat.z(), 4);
    Serial.println();
    
    // --- Periodic Calibration Status ---
    static int calib_counter = 0;
    if (++calib_counter >= 50) {
        calib_counter = 0;
        uint8_t sys, gyro, accel_cal, mag_cal;
        bno.getCalibration(&sys, &gyro, &accel_cal, &mag_cal);
        Serial.print("# CALIB: ");
        Serial.print(sys); Serial.print(",");
        Serial.print(gyro); Serial.print(",");
        Serial.print(accel_cal); Serial.print(",");
        Serial.println(mag_cal);
    }
    
    Serial.flush(); // Flush to ensure data is sent immediately
}

void collect_eit_frame()
    {
        // This function is called as often as possible in the main loop for Modes::EIT.
        // It measures the two impedance channels and stores the results in global variables.
        
        // --- Define Sensing Electrodes ---
        unsigned int senseAElectrode1 = 2, senseBElectrode1 = 3; // Channel 1
        unsigned int senseAElectrode2 = 4, senseBElectrode2 = 5; // Channel 2

        // --- Measure Impedance Channel 1 ---
        // Connect the selected sensing pair for the first channel
        senseAMux.select((ADG732::Channel) transformElectrode(senseAElectrode1));
        senseBMux.select((ADG732::Channel) transformElectrode(senseBElectrode1));
    
        // Trigger and wait for ADC operation
        adc_collect_samples(const_cast<uint32_t * >(g_aiSamples), g_iSamples);
    
        // Calculate magnitude and store it in the global variable
        g_fImpedanceMagnitude1 = eit_iq_demodulation ( 
            const_cast<uint32_t const * >(&g_aiSamples[g_iSample_rubbish]), // Ignore "rubbish" samples.
            g_iSamples_useful, 
            g_iSamples_per_cycle);
    
        // --- Measure Impedance Channel 2 ---
        // Connect the selected sensing pair for the second channel
        senseAMux.select((ADG732::Channel) transformElectrode(senseAElectrode2));
        senseBMux.select((ADG732::Channel) transformElectrode(senseBElectrode2));
        adc_collect_samples(const_cast<uint32_t * >(g_aiSamples), g_iSamples);
        g_fImpedanceMagnitude2 = eit_iq_demodulation ( 
            const_cast<uint32_t const * >(&g_aiSamples[g_iSample_rubbish]),
            g_iSamples_useful, 
            g_iSamples_per_cycle);

        // --- Stream EIT Data Immediately ---
        unsigned long currentTime = micros();
        Serial.print(currentTime); Serial.print(",");
        Serial.print(g_fImpedanceMagnitude1, 4); Serial.print(",");
        Serial.print(g_fImpedanceMagnitude2, 4);
        Serial.println();
        Serial.flush();
    }
