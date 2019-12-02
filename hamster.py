# Simple demo of reading each analog input from the ADS1x15 and printing it to
# the screen.
# Author: Tony DiCola
# License: Public Domain
import time

# Import the ADS1x15 module.
import Adafruit_ADS1x15

import bhstats
import json
import LightMQ
import requests


stats = [bhstats.BhStats(),bhstats.BhStats(),bhstats.BhStats(),bhstats.BhStats()]
messageQueue = LightMQ.LightMQ({"maxqueuelength": 999999, "persistencepath": "./lightMQ_hamster"})

# Create an ADS1115 ADC (16-bit) instance.
adc = Adafruit_ADS1x15.ADS1115()

# Choose a gain of 1 for reading voltages from 0 to 4.09V.
# Or pick a different gain to change the range of voltages that are read:
#  - 2/3 = +/-6.144V
#  -   1 = +/-4.096V
#  -   2 = +/-2.048V
#  -   4 = +/-1.024V
#  -   8 = +/-0.512V
#  -  16 = +/-0.256V
# See table 3 in the ADS1015/ADS1115 datasheet for more info on gain.
GAIN = 16
# Min change in ADC reading vs average for us to take notice.
MIN_CHANGE=4
# true fact
INCHES_PER_MILE=63360
WHEEL_CIRCUMFRANCE=[0,0,19.5,21]
# Define a maximum valid RPM reading, over which we classify the reading as invalid (sometimes events are sensed twice)
MAX_VALID_RPM=200
# If no revolutions are detected for this period of milliseconds or more, then RPM/MPH will be set to zero. 
WHEEL_STILLNESS_THRESHOLD = 2000

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

# Creates a new object with a copy of all fields in the fromObj EXCEPT fields with names specified in the exceptionList.
def objCopyExcept(fromObj,exceptionList):
  newObj = {}
  
  for thisKey in fromObj:
    if thisKey in exceptionList: 
      continue
    newObj[thisKey] = fromObj[thisKey]

  return newObj
  
# After making a copy of the stats and queueing the readings for shipment to the log collector, we need to reset things like distance. 
def resetWheelStats(idx):
  stats[idx].setStat("totalRevolutions",0)
  stats[idx].setStat("totalInches",0)
  # Even though the following two metrics are already reset by this time, through other means (stillness threshold was met), we'll reset them anyways. 
  stats[idx].setStat("rpm",0)
  stats[idx].setStat("mph",0)
 
  stats[idx].setStat("lastResetTime",getEpochMillis())

  stats[idx].setStat("runTimeSeconds",0)
  stats[idx].setStat("runStartTime",0)
  
  
# Queue readings from all analog wheel speed input sensors, then reset them. Run this function during times when the wheel has stopped for best results.
# ALSO: send those queued readings to the log collector.
def queueStatsReading(idx):
  # For each stats index
  # If the stats index is in use and has useful data
  # Then create a copy of it
  # Then add things like timestamp, runtime? rss? 
  # Then queue the reading for transmission to the server
  # Then try dequeueing and sending the reading to the server. IF successful pop the reading off the queue. 
  # LightMQ verbs: put, peek, pop - variable name messageQueue
  
  # Add an interval metric that reflects the period of time over which the metric covers.

  statsPeriod = 0
  if "lastResetTime" in stats[idx].getStats():
    statsPeriod = getEpochMillis() - stats[idx].getStat("lastResetTime")  
  else:
    statsPeriod = getEpochMillis() - stats[idx].getStat("startupTime")
  
  stats[idx].setStat("statsPeriod",statsPeriod)

  statsCopy = objCopyExcept(stats[idx].getStats(),["lastRevolutionTime","lastResetTime","startupTime","runStartTime"])
  statsCopy["timestamp"] = getEpochMillis()
  messageQueue.put(statsCopy)
  resetWheelStats(idx)
  dequeueReadings()
  dequeueReadings()
  # finished queueing a readings object.

def dequeueReadings():

  # If no readings, do nothing.
  if messageQueue.qsize() < 1:
    return

  # Try sending this
  print ("Queue peek: " + json.dumps(messageQueue.peek()))
  try:
    httpresp = requests.post("http://150.10.50.20:59655/hamsterwheel", json=messageQueue.peek())
  except Exception as e: 
    print ("EXCEPTION while posting data to log collector. e=" + str(e))
    return

  if httpresp.status_code != 200:
    print ("ERROR sending reading, status code=" + str(httpresp.status_code) + " body=" + httpresp.text)
    return

  print ("Successfully sent one reading to log collecrtor. DE-queueing one reading!")
  messageQueue.pop()

  # TODO: Catch-up logic, in case we need to "catch up" - send multiple readings per interval.
  


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
    stats[idx].setStat("totalInches",stats[idx].getStat("totalRevolutions") * WHEEL_CIRCUMFRANCE[idx])
    # The last revolution time metric is used by the loop to clear rpm&MPH if no movement has been detected in N seconds.
    stats[idx].setStat("lastRevolutionTime",getEpochMillis())

    # Make sure we track the start of the run, so we can also track run time elapsed.
    if "runStartTime" not in stats[idx].getStats():
      stats[idx].setStat("runStartTime",getEpochMillis())

    # not the first run, but run data has been cleared and we're starting a new run.
    if stats[idx].getStat("runStartTime") == 0:
      print("[" + str(idx) + "] New run starting...")
      stats[idx].setStat("runStartTime",getEpochMillis())

    # Keep updating the run time seconds metric, each revolution, as it may be the last of the run.
    runTimeMillis = getEpochMillis() - stats[idx].getStat("runStartTime")
    runTimeSeconds = (0.0 + runTimeMillis) / 1000
    runTimeSeconds = round(runTimeSeconds,2)
    stats[idx].setStat("runTimeSeconds",runTimeSeconds)

    # Don't calculate speed if wheel has been idle. But it still counts as a revolution (which we took care of above). 
    if timeSinceLastRevolution > WHEEL_STILLNESS_THRESHOLD:
        return

    print ("[" + str(idx) + "] " + json.dumps(stats[idx].getStats()))

    # Track max mph this run. 
    if "mph_max" in stats[idx].getStats():
      if mph > stats[idx].getStat("mph_max"):
        stats[idx].setStat("mph_max",mph)
    else:
      # no record of a max yet, current mph becomes max.
      stats[idx].setStat("mph_max",mph)
   
    # All sanity checks passed. This is a legitimate revolution.
    stats[idx].setStat("lastRevolutionMillis",timeSinceLastRevolution)
    stats[idx].averageStat("rpm",rpm)
    stats[idx].averageStat("mph",mph)
    stats[idx].averageStat("AvgAmtChange",amtChange)

# If the wheel is still, then we'll set RPM & MPH to zeros. 
def wheelIsStill(idx):
  # print ("Wheel " + str(idx) + " is idle.")

  # If RPM went from >0 to 0 then this counts as a "stop" - wheel was moving, then stopped. Count the number of times this happens per wheel.
  if "rpm" in stats[idx].getStats():
    if stats[idx].getStat("rpm") > 0:
      # stats[idx].incrementStat("stops")
      queueStatsReading(idx)

  stats[idx].setStat("rpm",0)
  stats[idx].setStat("mph",0)

# Check all wheels for stillness, taking action to update rate gauges on any wheels that are still.
def checkWheelStillness():
  for i in [2,3]:
    if "lastRevolutionTime" in stats[i].getStats():
      timeSinceLastRevolution = getEpochMillis() - stats[i].getStat("lastRevolutionTime")
      if timeSinceLastRevolution > WHEEL_STILLNESS_THRESHOLD:
        wheelIsStill(i)
    else:
      # last revolution time has not yet been set. Set values to zero since that indicates it's still.
      wheelIsStill(i)




valuesAvg=[0.0,0.0,0.0,0.0,0.0]
direction=[0,0,0,0]
startTime = getEpochMillis()
lastRuntimeStatsPrinted = startTime
loops=0
stats[2].setStat("startupTime",getEpochMillis())
stats[3].setStat("startupTime",getEpochMillis())
while True:
    loops = loops + 1
    runtimeElapsedSeconds = int((getEpochMillis() - startTime)/1000)
    # This block started as a periodic metrics print, but evolved into a "stillness" detection block. If wheel has been idle, then it sets speed/rpm to zero. 
    if runtimeElapsedSeconds % 2 == 0 and runtimeElapsedSeconds > 0 and getEpochMillis() - lastRuntimeStatsPrinted > 1000:
      loopsPerSecond = loops / runtimeElapsedSeconds
      #print ("Runtime Stats: " + str(loops) + " in " + str(runtimeElapsedSeconds) + " seconds = " + str(loopsPerSecond) + " loops per second")
      #print ("avg2=" + str(valuesAvg[2]))
      #print ("avg3=" + str(valuesAvg[3]))
      lastRuntimeStatsPrinted = getEpochMillis()
      checkWheelStillness()

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
