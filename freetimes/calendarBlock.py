import arrow
import timeBlock
class calendarBlock(object):
    startTime = None
    endTime = None
    name = ""
    calendar = ""
    ID = None
    def __init__(self,start,end,nayme,caylendar,eyeD):
        self.startTime = start
        self.endTime = end
        self.name = nayme
        self.calendar = caylendar
        self.ID = eyeD
    def isIn(self,timeblock):
        if (self.startTime < timeblock.startTime):
            #if this event starts before the timeblock does
            if(self.endTime > timeblock.startTime):
                #if this event starts before and ends inside the time block
                return True
            else:
                #event starts and ends before this timeblock
                return False
        else:
            #the event starts after the timeblock does
            if(self.startTime < timeblock.endTime):
                #if the event starts after timeblock does but sometime inside of the timeBlock
                return True
            elif(self.endTime < timeblock.endTime):
                #if this event starts after the timeblock but ends before the timeblock ends
                return True
            else:
                #this event starts after and ends after
                return False
    def toTblock(self):
        tblock = timeBlock.make_timeBlock(self.startTime, self.endTime)

def make_calendarBlock(start,end,nayme,caylendar,eyeD):
    calBlock = calendarBlock(start,end,nayme,caylendar,eyeD)
    return calBlock
