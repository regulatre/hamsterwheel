# Simple demo of reading each analog input from the ADS1x15 and printing it to
# the screen.
# Author: Tony DiCola
# License: Public Domain
import time

# Import the ADS1x15 module.
import Adafruit_ADS1x15


# Create an ADS1115 ADC (16-bit) instance.
adc = Adafruit_ADS1x15.ADS1115()

# Or create an ADS1015 ADC (12-bit) instance.
#adc = Adafruit_ADS1x15.ADS1015()

# Note you can change the I2C address from its default (0x48), and/or the I2C
# bus by passing in these optional parameters:
#adc = Adafruit_ADS1x15.ADS1015(address=0x49, busnum=1)

# Choose a gain of 1 for reading voltages from 0 to 4.09V.
# Or pick a different gain to change the range of voltages that are read:
#  - 2/3 = +/-6.144V
#  -   1 = +/-4.096V
#  -   2 = +/-2.048V
#  -   4 = +/-1.024V
#  -   8 = +/-0.512V
#  -  16 = +/-0.256V
# See table 3 in the ADS1015/ADS1115 datasheet for more info on gain.
GAIN = 1
# Min change in ADC reading vs average for us to take notice.
MIN_CHANGE=4

# This function gets fired every time a "revolution" is detected - one complete turn around, or one pass of the hall-effect sensor.
def revolutionEvent(idx):
    print ("TODO: One Revolution just occurred! IDX=" + str(idx))
    pass
    

print('Reading ADS1x15 values, press Ctrl-C to quit...')
# Print nice channel column headers.
print('| {0:>6} | {1:>6} | {2:>6} | {3:>6} |'.format(*range(4)))
print('-' * 37)
# Main loop.
valuesAvg=[0.0,0.0,0.0,0.0,0.0]
direction=[0,0,0,0]
while True:
    # Read all the ADC channel values in a list.
    values = [0]*4
    # for i in range(4):
    # Just loop through the analog pins that have hall-effect speed-ometer sensors attached.
    for i in [2,3]:
        # Read the specified ADC channel using the previously set gain value.
        values[i] = adc.read_adc(i, gain=GAIN)
        valuesAvg[i] = (valuesAvg[i] + values[i]) / 2
        # Note you can also pass in an optional data_rate parameter that controls
        # the ADC conversion time (in samples/second). Each chip has a different
        # set of allowed data rate values, see datasheet Table 9 config register
        # DR bit values.
        #values[i] = adc.read_adc(i, gain=GAIN, data_rate=128)
        # Each value will be a 12 or 16 bit signed integer value depending on the        
        # ADC (ADS1015 = 12-bit, ADS1115 = 16-bit).
        amtChange = values[i] - valuesAvg[i]

        if (i==3 or i==2) and amtChange > MIN_CHANGE and direction[i] != 1:
            print ("[A" + i + "]: " + str(amtChange) + " from " + str(values[i]) + " to " + str(valuesAvg[i]))
            revolutionEvent(i)
            # IMPORTANT: Upon detecting a pass/revolution we start a mandatory "delay" before checking anything again. This effectivelu de-bounces the readings. 
            time.sleep(0.2)
        
        if amtChange > MIN_CHANGE:
            direction[i]=1
        if amtChange < 0:
            direction[i]=-1

    ANALOG_INDEX=3
