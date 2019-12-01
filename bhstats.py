

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

