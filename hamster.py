# Simple demo of reading each analog input from the ADS1x15 and printing it to
# the screen.
# Author: Tony DiCola
# License: Public Domain
import time

# Import the ADS1x15 module.
import Adafruit_ADS1x15

import bhstats
import json

stats = [bhstats.BhStats(),bhstats.BhStats(),bhstats.BhStats(),bhstats.BhStats()]

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
# true fact
INCHES_PER_MILE=63360
WHEEL_CIRCUMFRANCE=[0,0,19.5,21]
# Define a maximum valid RPM reading, over which we classify the reading as invalid (sometimes events are sensed twice)
MAX_VALID_RPM=200

def getEpochMillis():
    # time.time() returns a float, expressed in terms of seconds, but multiplying by 1000 gives us a pretty accurate milliseconds.
    return int(round(time.time() * 1000))

def logStdErr (yourMessage):
    # python2 syntax
    print >> sys.stderr, yourMessage
    # Python3: print yourMessage, file=sys.stderr

def getRPMFromOneRoundTime(oneRoundTimeMillis):
  rpm = (1000 * 60) / oneRoundTimeMillis
  rpm = round(rpm,3)
  return rpm

def getMPHFromRPM(rpm,inchesPerRevolution):
  mph = (rpm * inchesPerRevolution * 60) / INCHES_PER_MILE
  mph = round(mph,3)
  return mph


# Initialize an array that we'll use to store last revolution times for each analog input.
LAST_REVOLUTION_TIME = [getEpochMillis(), getEpochMillis(), getEpochMillis(), getEpochMillis()]
# This function gets fired every time a "revolution" is detected - one complete turn around, or one pass of the hall-effect sensor.
def revolutionEvent(idx,amtChange):
    timeSinceLastRevolution=getEpochMillis()-LAST_REVOLUTION_TIME[idx];
    LAST_REVOLUTION_TIME[idx] = getEpochMillis()
    
    rpm = getRPMFromOneRoundTime(timeSinceLastRevolution)
    mph = getMPHFromRPM(rpm,WHEEL_CIRCUMFRANCE[idx])

    # Make sure each stats array contains an element that reflects the analog index to which it corresponds.
    stats[idx].setStat("analogIndex",idx)

    if rpm > MAX_VALID_RPM:
        return

    # Don't count this as a revolution unless above sanity checks and debouncing logic pass. 
    stats[idx].incrementStat("totalRevolutions")

    # Don't calculate speed if wheel has been idle. But it still counts as a revolution (which we took care of above). 
    if timeSinceLastRevolution > 5000:
        return

    print ("[" + str(idx) + "] TODO: Calibrate wheel circumfrance array. STATS=" + json.dumps(stats[idx].getStats()))
    
    # All sanity checks passed. This is a legitimate revolution.
    stats[idx].setStat("lastRevolutionMillis",timeSinceLastRevolution)
    stats[idx].setStat("rpm",rpm)
    stats[idx].setStat("mph",mph)
    stats[idx].averageStat("AvgAmtChange",amtChange)

valuesAvg=[0.0,0.0,0.0,0.0,0.0]
direction=[0,0,0,0]
while True:
    # Read all the ADC channel values in a list.
    values = [0]*4
    # loop through the analog pins that have hall-effect speed-ometer sensors attached.
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
            # print ("[A" + str(i) + "]: " + str(amtChange) + " from " + str(values[i]) + " to " + str(valuesAvg[i]))
            revolutionEvent(i,amtChange)
            # NOTE: We were sleeping for 0.2 here when it was just one input. With multiple inputs we need to do an elapsed time check instead of a sleep. That way inputs don't interfere with eachother.
        
        if amtChange > MIN_CHANGE:
            direction[i]=1
        if amtChange < 0:
            direction[i]=-1

    ANALOG_INDEX=3
