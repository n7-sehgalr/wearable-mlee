
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
    // Serial.print("\r\nmagnitudes: ");
    Serial.flush();

    // Disable Outputs
    driveSourceMux.enable(false);
    driveGroundMux.enable(false);
    senseAMux.enable(false);
    senseBMux.enable(false);


    unsigned int drivingElectrode = 0, groundElectrode = 1; // Physical pins 1, 3


    // Connect the selected driving pair
    driveSourceMux.select((ADG732::Channel) transformElectrode(drivingElectrode)); // Setup the drive current "+/source" multiplexer
    driveGroundMux.select((ADG732::Channel) transformElectrode(groundElectrode )); // Setup the drive current "-/ground" multiplexer
    driveGroundMux.enable(true); driveSourceMux.enable(true); // Enable both drive current multiplexers

    // unsigned int senseAElectrode = 2, senseBElectrode = 3; // Physical pins 5, 7
        
// Loop over all driving pairs
for(;;)
    {
    // Loop over all sensing pairs for the current driving arrangement :
    for (   unsigned int sense_pin = 2; sense_pin < 6; sense_pin += 2)
        {
            unsigned int senseAElectrode = sense_pin, senseBElectrode = sense_pin + 1; // Physical pins 5, 7, 9, 11
            // Connect the selected sensing pair
            senseAMux.select((ADG732::Channel) transformElectrode(senseAElectrode)); // Setup the sense "A" multiplexer
            senseBMux.select((ADG732::Channel) transformElectrode(senseBElectrode)); // Setup the sense "B" multiplexer
            senseAMux.enable(true); senseBMux.enable(true); // Enable both sense multiplexers

            // Trigger and wait for ADC operation
            adc_collect_samples(const_cast<uint32_t * >(g_aiSamples), g_iSamples);

            // Disable both sensing multiplexers
            senseAMux.enable(false); senseBMux.enable(false);

            // Calculate magnitude
            float magnitude = eit_iq_demodulation ( 
                const_cast<uint32_t const * >(&g_aiSamples[g_iSample_rubbish]), // Ignore "rubbish" samples. (impacted by mux settling time)
                g_iSamples_useful, 
                g_iSamples_per_cycle);

            // TODO: calculate Z using the phase offset
            // Z = complex division of Voltage and Current

            // Write output to usb and flush immediately so that USB interrupts do not impact ADC timings
            Serial.print(magnitude, 4); Serial.print(", ");Serial.flush();
        }

    // Disable both drive and sensing multiplexers
    // driveSourceMux.enable(false);
    // driveGroundMux.enable(false);
    // senseAMux.enable(false);
    // senseBMux.enable(false);
    Serial.print("\r\n"); Serial.flush();
    }
}