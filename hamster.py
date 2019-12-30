

# Thank you to Adafruit, and Tony DiCola for writing the ADS1115 ADC code that served as the starting point for this application. 

import time

import Adafruit_ADS1x15

import bhstats
import json
import LightMQ
import requests

# for environment variables.
import os
# for terminating upon fatal error
import sys


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

# Can be set to True via env variable, to generate copious amounts of analog debugging detail.
DEBUG_ANALOG=False
# Must be set via environment.
EVENT_RECEIVER_URL=""

# true fact
INCHES_PER_MILE=63360
## circumfrences must be set via environment
WHEEL_CIRCUMFRENCE=[] 
# Indexes present will be set to include the indexes for which circumfrences are specified. Any index missing a circumfrence is assumed to not be present.
WHEEL_INDEXES_PRESENT = []
# Define a maximum valid RPM reading, over which we classify the reading as invalid (sometimes events are sensed twice)
MAX_VALID_RPM=200
# If no revolutions are detected for this period of milliseconds or more, then RPM/MPH will be set to zero. 
WHEEL_STILLNESS_THRESHOLD = 2000

def die (lastMessage):
  print ("FATAL ERROR: " + lastMessage)

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
  stats[idx].setStat("mph_max",0)
 
  stats[idx].setStat("lastResetTime",getEpochMillis())

  stats[idx].setStat("runTimeSeconds",0)
  stats[idx].setStat("runStartTime",0)

  stats[idx].setStat("crazyHighRPMEvents",0)
  
  stats[idx].resetArray("dbgRevolutionRPM")
  stats[idx].resetArray("dbgRevolutionAmtChange")
  stats[idx].resetArray("dbgAmtChangedFrom")
  
  stats[idx].resetMinMax("amtChange")
  stats[idx].resetMinMax("amtChangeIdle")
  

  
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
  statsCopy["appUptimeSeconds"] = getAppUptimeSeconds()
  messageQueue.put(statsCopy)

  # Dequeue up to N items at a time as needed. TODO: Do this asychronously, in an independent thread, that won't disrupt the main loop. 
  if (messageQueue.qsize() > 0):
    itemCountToSend = messageQueue.qsize()
    if itemCountToSend > 10:
      itemCountToSend = 10
  for i in range(itemCountToSend):
      success = dequeueOneReading()
      if messageQueue.qsize() > 0: 
        print ("Attempted dequeue. success=" + str(success) + " qsize=" + str(messageQueue.qsize()))
      # Connection is down. Don't try any more this round. Let the main loop do its work a bit more.
      if success == False:
        break


# Return False if anything goes wrong. If false is returned, you shouldn't keep trying to dequeue messages, rather wait and try again later.
def dequeueOneReading():
  global EVENT_RECEIVER_URL

  # If no readings, do nothing.
  if messageQueue.qsize() < 1:
    return True

  # Try sending this
  try:
    augmentedEventObject = objCopyExcept(messageQueue.peek(),[])
    # the timestamp field is set when the message is added to the queue, so it provides a very accurate point of reference to calculate queued time.
    augmentedEventObject["queuedms"] = getEpochMillis() - augmentedEventObject["timestamp"]
    print ("TRANSMITTING EVENT: " + json.dumps(augmentedEventObject))
    httpresp = requests.post(EVENT_RECEIVER_URL, json=augmentedEventObject)
  except Exception as e: 
    print ("EXCEPTION while posting data to log collector. e=" + str(e))
    return False

  if httpresp.status_code != 200:
    print ("ERROR sending reading, status code=" + str(httpresp.status_code) + " body=" + httpresp.text)
    return False

  print ("Successfully sent one reading to log collector. DE-queueing one reading!")
  messageQueue.pop()
  return True

  # TODO: Catch-up logic, in case we need to "catch up" - send multiple readings per interval.
  


# Initialize an array that we'll use to store last revolution times for each analog input.
LAST_REVOLUTION_TIME = [getEpochMillis(), getEpochMillis(), getEpochMillis(), getEpochMillis()]
# This function gets fired every time a "revolution" is detected - one complete turn around, or one pass of the hall-effect sensor.
def revolutionEvent(idx,amtChange):
    global WHEEL_CIRCUMFRENCE
    global MAX_VALID_RPM
    global WHEEL_STILLNESS_THRESHOLD

    timeSinceLastRevolution=getEpochMillis()-LAST_REVOLUTION_TIME[idx]
    LAST_REVOLUTION_TIME[idx] = getEpochMillis()
    
    rpm = getRPMFromOneRoundTime(timeSinceLastRevolution)
    mph = getMPHFromRPM(rpm,WHEEL_CIRCUMFRENCE[idx])

    # Make sure each stats array contains an element that reflects the analog index to which it corresponds.
    stats[idx].setStat("analogIndex",idx)
    
    

    # Record detailed per-revolution amtChange readings.
    stats[idx].appendArray("dbgRevolutionRPM",     rpm)
    if rpm > MAX_VALID_RPM:
        # Record the invalid RPM event with a special annotation.
        stats[idx].appendArray("dbgRevolutionAmtChange","!" + str(round(amtChange,2)) + "!")
        stats[idx].incrementStat("crazyHighRPMEvents")
        return
    else:
        stats[idx].appendArray("dbgRevolutionAmtChange",str(round(amtChange,2)))


    # Don't count this as a revolution unless above sanity checks and debouncing logic pass. 
    stats[idx].incrementStat("totalRevolutions")
    stats[idx].setStat("totalInches",stats[idx].getStat("totalRevolutions") * WHEEL_CIRCUMFRENCE[idx])
    # The last revolution time metric is used by the loop to clear rpm&MPH if no movement has been detected in N seconds.
    stats[idx].setStat("lastRevolutionTime",getEpochMillis())

    # Make sure we track the start of the run, so we can also track run time elapsed.
    if "runStartTime" not in stats[idx].getStats():
      stats[idx].setStat("runStartTime",getEpochMillis())

    # not the first run, but run data has been cleared and we're starting a new run.
    if stats[idx].getStat("runStartTime") == 0:
      print("[" + str(idx) + "] New run starting... amtChange=" + str(amtChange))
      stats[idx].setStat("runStartTime",getEpochMillis())
      stats[idx].setStat("runStartAmtChange",amtChange)

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

  # Wheel may be still, but has it even moved at all? If so then it's worth recording. Otherwise not so much. In any case we reset the stats for the wheel before returning.
  if "runTimeSeconds" in stats[idx].getStats():
    if stats[idx].getStat("runTimeSeconds") > 0:
      # stats[idx].incrementStat("stops")
      queueStatsReading(idx)

  resetWheelStats(idx)

# Check all wheels for stillness, taking action to update rate gauges on any wheels that are still.
def checkWheelStillness():
  for i in WHEEL_INDEXES_PRESENT:
    if "lastRevolutionTime" in stats[i].getStats():
      timeSinceLastRevolution = getEpochMillis() - stats[i].getStat("lastRevolutionTime")
      if timeSinceLastRevolution > WHEEL_STILLNESS_THRESHOLD:
        wheelIsStill(i)
    else:
      # last revolution time has not yet been set. Set values to zero since that indicates it's still.
      wheelIsStill(i)

def doStartupSanityChecks():

  global DEBUG_ANALOG
  global WHEEL_STILLNESS_THRESHOLD
  global GAIN
  global MAX_VALID_RPM
  global EVENT_RECEIVER_URL
  global WHEEL_INDEXES_PRESENT
  global WHEEL_CIRCUMFRENCE
  global MIN_CHANGE

  if "DEBUG_ANALOG" in os.environ and os.environ["DEBUG_ANALOG"].lower() == "true": 
    DEBUG_ANALOG=True
  else: 
    DEBUG_ANALOG=False


  if "WHEEL_STILLNESS_THRESHOLD" in os.environ:
    WHEEL_STILLNESS_THRESHOLD = float(os.environ["WHEEL_STILLNESS_THRESHOLD"])
    print ("Overriding wheel stillness threshold with value from environment: " + json.dumps(WHEEL_STILLNESS_THRESHOLD))

  if "GAIN" in os.environ:
    GAIN=float(os.environ["GAIN"])
    print ("Overriding ADC GAIN with value from environment: " + json.dumps(GAIN))

  if "MAX_VALID_RPM" in os.environ:
    MAX_VALID_RPM=float(os.environ["MAX_VALID_RPM"])
    print ("Overriding MAX_VALID_RPM with value from environment: " + json.dumps(MAX_VALID_RPM))

  if "EVENT_RECEIVER_URL" not in os.environ:
    die ("ERROR: Please set env variable EVENT_RECEIVER_URL to the logstash URL to which we should post events.")
    sys.exit(2)
  else:
    EVENT_RECEIVER_URL=os.environ["EVENT_RECEIVER_URL"]
    print ("Event receiver URL: " + json.dumps(EVENT_RECEIVER_URL))

  if "MIN_CHANGE" in os.environ:
    MIN_CHANGE = float(os.environ["MIN_CHANGE"])
    print ("Overriding MIN_CHANGE with value from environment. New value: " + str(MIN_CHANGE))

  if "WHEEL_CIRCUMFRENCE" not in os.environ:
    die ("ERROR: Please set env variable WHEEL_CIRCUMFRENCE to four floating point values eg. 0,0,19.5,21.0")
    sys.exit(2)
  else:
    WHEEL_CIRCUMFRENCE=[0,0,0,0]
    circumfrence_strings_array = os.environ["WHEEL_CIRCUMFRENCE"].split(",")
    WHEEL_CIRCUMFRENCE[0] = float(circumfrence_strings_array[0])
    WHEEL_CIRCUMFRENCE[1] = float(circumfrence_strings_array[1])
    WHEEL_CIRCUMFRENCE[2] = float(circumfrence_strings_array[2])
    WHEEL_CIRCUMFRENCE[3] = float(circumfrence_strings_array[3])
    print ("Wheel Circumfrences: " + json.dumps(WHEEL_CIRCUMFRENCE))

  # Create an array with values like this: [0] [2,3] etc - indexes represent the analog indexes that are present.
  WHEEL_INDEXES_PRESENT=[]
  if WHEEL_CIRCUMFRENCE[0] > 0: WHEEL_INDEXES_PRESENT.append(0)
  if WHEEL_CIRCUMFRENCE[1] > 0: WHEEL_INDEXES_PRESENT.append(1)
  if WHEEL_CIRCUMFRENCE[2] > 0: WHEEL_INDEXES_PRESENT.append(2)
  if WHEEL_CIRCUMFRENCE[3] > 0: WHEEL_INDEXES_PRESENT.append(3)
  print ("Wheel / Analog Inputs present: " + json.dumps(WHEEL_INDEXES_PRESENT))



def getAppUptimeSeconds():
  uptimeMillis = getEpochMillis() - APP_START_TIME
  uptimeSeconds = round(uptimeMillis / 1000)
  return uptimeSeconds



APP_START_TIME=getEpochMillis()
doStartupSanityChecks()
valuesAvg=[0.0,0.0,0.0,0.0,0.0]
direction=[0,0,0,0]
startTime = getEpochMillis()
lastRuntimeStatsPrinted = startTime
loops=0
stats[0].setStat("startupTime",getEpochMillis())
stats[1].setStat("startupTime",getEpochMillis())
stats[2].setStat("startupTime",getEpochMillis())
stats[3].setStat("startupTime",getEpochMillis())
print ("READY SET GO!!!")
loopsPerSecond=0
while True:
    loops = loops + 1
    runtimeElapsedSeconds = int((getEpochMillis() - startTime)/1000)
    # This block started as a periodic metrics print, but evolved into a "stillness" detection block. If wheel has been idle, then it sets speed/rpm to zero. 
    if runtimeElapsedSeconds % 2 == 0 and runtimeElapsedSeconds > 0 and getEpochMillis() - lastRuntimeStatsPrinted > 1000:
      loopsPerSecond = loops / runtimeElapsedSeconds
      if DEBUG_ANALOG==True:
          print ("ANALOG DEBUG: loops=" + str(loops) + " in " + str(runtimeElapsedSeconds) + " seconds = " + str(loopsPerSecond) + " loops per second")
      #print ("avg2=" + str(valuesAvg[2]))
      #print ("avg3=" + str(valuesAvg[3]))
      lastRuntimeStatsPrinted = getEpochMillis()
      checkWheelStillness()

    # Read all the ADC channel values in a list.
    values = [0]*4
    # loop through the analog pins that have hall-effect speed-ometer sensors attached.
    for i in WHEEL_INDEXES_PRESENT:
        # Read the specified ADC channel using the previously set gain value.
        values[i] = adc.read_adc(i, gain=GAIN)
        # Note you can also pass in an optional data_rate parameter that controls
        # the ADC conversion time (in samples/second). Each chip has a different
        # set of allowed data rate values, see datasheet Table 9 config register
        # DR bit values.
        #values[i] = adc.read_adc(i, gain=GAIN, data_rate=128)
        # Each value will be a 12 or 16 bit signed integer value depending on the        
        # ADC (ADS1015 = 12-bit, ADS1115 = 16-bit).
        valuesAvg[i] = (valuesAvg[i] + values[i]) / 2
        amtChange = values[i] - valuesAvg[i]
        if DEBUG_ANALOG==True:
          print ("avg[" + str(i) + "]=" + str(round(valuesAvg[i],2)) + " current=" + str(round(values[i],2)) + " chg=" + str(round(amtChange,2)))

        if amtChange > MIN_CHANGE and direction[i] != 1:
            # print ("[A" + str(i) + "]: " + str(round(amtChange,2)) + " from " + str(round(values[i],2)) + " to " + str(round(valuesAvg[i],2)))
            revolutionEvent(i,amtChange)
            stats[i].averageStat("sampleRate",loopsPerSecond)
            stats[i].appendArray("dbgAmtChangedFrom",valuesAvg[i])
            stats[i].recordMinMax("amtChange",amtChange)
            # in the past we had a time.sleep() here, but then we evolved to a time check method. Ultimately we should use a separate threads for checking ADC and processing readings.
        else:
            stats[i].recordMinMax("amtChangeIdle",amtChange)
        
        
        if amtChange > MIN_CHANGE:
            direction[i]=1
        if amtChange < (0-MIN_CHANGE) :
            direction[i]=-1


