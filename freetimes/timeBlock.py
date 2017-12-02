import arrow

class timeBlock(object):
    startTime = None
    endTime = None
    events = []
    isFull = False
    def __init__(self,start,end):
        self.startTime = start
        self.endTime = end
    def addEvent(self, someEvent):
        self.events.append(someEvent)
    def busy(self):
        self.isFull = True
    def isBusy(self):
        return self.isFull
    def isIn(self,tblock):
        if(tblock.startTime == self.startTime or tblock.endTime == self.endTime):
            return True
        elif (tblock.startTime < self.startTime):
            if (tblock.endTime > self.startTime):
                return True
        else:
            if(tblock.startTime < self.endTime):
                return True
        return False


def make_timeBlock(start,end):
    timeblock = timeBlock(start, end)
    return timeblock
