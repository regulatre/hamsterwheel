

# A simple class for collecting application statistics into a dictionary object.


class BhStats():
    def __init__(self):
      self.STATS = {}

    def setStat(self,statName,statValue):
        self.STATS[statName] = statValue
        # log("STAT: " + statName + " = " + str(statValue))

    def getStat(self,statName):
        if (statName in self.STATS):
          return self.STATS[statName]
        else:
          return 0

    def incrementStat(self,statName):
        if (statName in self.STATS):
            self.STATS[statName] = self.STATS[statName] + 1
        else:
            self.STATS[statName] = 1


    def getStats(self):
      return self.STATS
 
    def averageStat(self,statName,newValue):
      if statName in self.STATS:
        # do averaging
        self.STATS[statName] = round( (self.STATS[statName] + newValue) / 2, 3)
      else:
        # First value being added, add as-is.
        self.STATS[statName] = newValue

    # Append the given <any datatype> to an ever growing array under the statName key
    def appendArray(self,statName,newArrayElement):
      if statName in self.STATS:
        # Append to existing array.
        self.STATS[statName].append(newArrayElement)
      else:
        # new array
        self.STATS[statName] = [ newArrayElement ]
        
    # A convenience function for resetting an array back to nothing.
    def resetArray(self,statName):
      self.STATS[statName] = []
      
    def recordMin(self,statBaseName,newMinValue):
      self.STATS[statBaseName + "_min"] = newMinValue
      pass
    
    def recordMax(self,statBaseName,newMaxValue):
      self.STATS[statBaseName + "_max"] = newMaxValue
      pass
    
    # Given a stat base name, and current reading, we'll track <basename>_min and <basename>_max for you.
    def recordMinMax(self,statBaseName,newValue):
      if (statBaseName + "_min") not in self.STATS:
        self.recordMin(statBaseName,newValue)
        return
      if (statBaseName + "_max") not in self.STATS:
        self.recordMax(statBaseName,newValue)
        return
      
      if newValue > self.STATS[statBaseName + "_max"]:
        self.recordMax(statBaseName,newValue)
        
      if newValue < self.STATS[statBaseName + "_min"]:
        self.recordMin(statBaseName,newValue)
        
      # end of recordMinMax. 
      
    def resetMinMax(self,statBaseName):
      if (statBaseName + "_min") in self.STATS: del self.STATS[statBaseName + "_min"]
      if (statBaseName + "_max") in self.STATS: del self.STATS[statBaseName + "_max"]
      
