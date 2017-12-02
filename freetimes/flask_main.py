import flask
from flask import render_template
from flask import request
from flask import url_for
import uuid
from random import randint
import json
import logging

# Date handling
import arrow # Replacement for datetime, based on moment.js
# import datetime # But we still need time
from dateutil import tz  # For interpreting local times

from pymongo import MongoClient
# OAuth2  - Google library implementation for convenience
from oauth2client import client
import httplib2   # used in oauth2 flow

# Google API for services
from apiclient import discovery

import timeBlock
import calendarBlock

###
# Globals
###
import config
if __name__ == "__main__":
    CONFIG = config.configuration()
else:
    CONFIG = config.configuration(proxied=True)

app = flask.Flask(__name__)
app.debug=CONFIG.DEBUG
app.logger.setLevel(logging.DEBUG)
app.secret_key=CONFIG.SECRET_KEY
calendar = []
idlist = []
SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
CLIENT_SECRET_FILE = CONFIG.GOOGLE_KEY_FILE  ## You'll need this
APPLICATION_NAME = 'MeetMe class project'
#mongodb://<dbuser>:<dbpassword>@ds129090.mlab.com:29090/cis322calendarapp
MONGO_CLIENT_URL = "mongodb://{}:{}@{}:{}/{}".format(
    CONFIG.DB_USER,
    CONFIG.DB_USER_PW,
    CONFIG.DB_HOST,
    CONFIG.DB_PORT,
    CONFIG.DB)
CURRENT_MEET_ID = -1
CURRENT_BUSY_LIST = []
ADMIN_ID = -1
#
#  Pages (routed from URLs)
#
#############################

@app.route("/")
@app.route("/index")
def index():
    app.logger.debug("Entering Index")
    return render_template("index.html")
@app.route("/main")
def main():
    app.logger.debug("Entering main")
    dbclient = MongoClient(MONGO_CLIENT_URL)
    db = getattr(dbclient, CONFIG.DB)
    collection = db.meets
    myData = collection.find({"user_id":CURRENT_MEET_ID})
    app.logger.debug("Got the database")
    service = get_gcal_service(valid_credentials())
    if 'begin_date' not in flask.session:
        init_session_values()
    busyDict = [] #array of dicts mentioned in fixme
    cblockList = [] #list of relevant calendar blocks
    tblockList = [] #List of all tblocks between the dates selected
    freetblockList = [] #consolidated free tblocks
    somelist = []
    if calendar:
        #if there is at least one calendar id selected
        app.logger.debug("at least one calendar selected")
        page_token = None
        for cal in calendar:
            #loop through all the calendadr id's
            while True:
                #loop through all of the events in the calendars
                events = service.events().list(calendarId = cal, pageToken = page_token, timeMin=flask.session['begin_date'], timeMax=flask.session['end_date']).execute()
                for event in events['items']:
                    cont = False
                    if idlist:
                        for item in idlist:
                            if event['id'] == item:
                                cont = True
                    if cont:
                        continue #ignore this event if the id is in an event ignore list
                    #get relevant event information
                    #print("***************************************************{}*************************************************".format(event))
                    if 'dateTime' in event['start']:
                        eventStart = arrow.get(event['start']['dateTime'])
                        eventEnd = arrow.get(event['end']['dateTime'])
                    else:
                        eventStart = arrow.get(event['start']['date'])
                        eventEnd = arrow.get(event['end']['date'])
                    if eventStart < arrow.get(flask.session['end_date']):
                        if eventEnd > arrow.get(flask.session['begin_date']):
                            #if the event is in range
                            #now need to check if its transparent
                            if 'transparency' in event:
                                continue
                            else:
                                eventDict = {
                                             'start':eventStart.format('YYYY-MM-DD HH:mm'),
                                             'end': eventEnd.format('YYYY-MM-DD HH:mm'),
                                             'event': event['summary'],
                                             'calendar': (service.calendars().get(calendarId = cal).execute())['summary'],
                                             'id':event['id']
                                            }
                                busyDict.append(eventDict)
                                cblockList.append(calendarBlock.make_calendarBlock(eventStart,eventEnd,event['summary'],(service.calendars().get(calendarId = cal).execute())['summary'],event['id']))
                                somelist.append(timeBlock.make_timeBlock(eventStart,eventEnd))
                page_token = events.get('nextPageToken')
                if not page_token:
                    break
        global CURRENT_BUSY_LIST
        CURRENT_BUSY_LIST = somelist
        #collection.remove({'user_id':CURRENT_MEET_ID})
        #newDict = {
        #"type":"admin",
        #"collective_free_times":[],
        #"busy_list":somelist,
        #"user_id":CURRENT_MEET_ID
        #}
        #collection.insert(newDict)

        #now I have a cblock list full of calendar blocks...
        #now I need to make a list of timeblocks such that there
        #is 15 minutes space between them
        iterateDate = arrow.get(flask.session['begin_date'])
        while iterateDate < arrow.get(flask.session['end_date']):
            tblockList.append(timeBlock.make_timeBlock(iterateDate, iterateDate.shift(minutes=+15)))
            iterateDate = iterateDate.shift(minutes=+15)
        #now I have a list of timeblocks in tblockList
        userFreeTimes = []
        lastBlock = True
        tstart = None
        #FIXME multiple failed attempts at generating list of freetimes...
        #tend = None
        #for calEvent in cblockList:
        #    for tblock in tblockList:
        #        if calEvent.isIn(tblock):
        #            tblock.busy()
        #            if (lastBlock == False):
        #                tstart = tblock.startTime
        #            lastBlock = True
        #        else:
        #            if (lastBlock == True):
        #                block=timeBlock.make_timeBlock(tstart,tblock.endTime)
        #                tstart = None
        #                userFreeTimes.append(block)
        #            lastBlock = False
        #now all the tblocks are set up to be busy or not busy
        #just need the logic to seperate them

        #print("*************************{},{},{}*****************".format(tblockList[131].startTime,tblockList[131].endTime,tblockList[131].isFull))
        #while i < len(tblockList):
        #    if not tstart and tblockList[i].isBusy():
        #        continue
        #    elif tblockList[i].isBusy():
        #        freetblockList.append(timeBlock.make_timeBlock(tstart,tend))
        #        tstart = None
        #        tend = None
        #    elif not tstart:
        #        tstart = tblockList[i].startTime
        #        tend = tblockList[i].endTime
        #    else:
        #        tend = tblockList[i].endTime
        #    if i==len(tblockList)-1 and not tblockList[i].isFull():
        #        freetblockList.append(tstart,tend)
        #    app.logger.debug(i)
        #    app.logger.debug(len(tblockList))
    app.logger.debug("exited while loop")
    if busyDict:
        flask.g.busyTimes = busyDict
    if userFreeTimes:
        #now I want the start/end times of freetblockList as isostrings in an
        #array of 2 item dicts
        submitList = []
        for item in userFreeTimes:
            myDict = {
                'start':item.startTime.isoformat(),
                'end':item.endTime.isoformat()
            }
            submitList.append(myDict)
        flask.g.freeList = submitList
    return render_template('main.html')

@app.route("/main2.html")
def main2():
    app.logger.debug("Entering main")
    dbclient = MongoClient(MONGO_CLIENT_URL)
    db = getattr(dbclient, CONFIG.DB)
    collection = db.meets
    myData = collection.find({"user_id":CURRENT_MEET_ID})
    app.logger.debug("Got the database")
    service = get_gcal_service(valid_credentials())
    if 'begin_date' not in flask.session:
        init_session_values()
    busyDict = [] #array of dicts mentioned in fixme
    cblockList = [] #list of relevant calendar blocks
    tblockList = [] #List of all tblocks between the dates selected
    freetblockList = [] #consolidated free tblocks
    somelist = []
    if calendar:
        #if there is at least one calendar id selected
        app.logger.debug("at least one calendar selected")
        page_token = None
        for cal in calendar:
            #loop through all the calendadr id's
            while True:
                #loop through all of the events in the calendars
                events = service.events().list(calendarId = cal, pageToken = page_token, timeMin=flask.session['begin_date'], timeMax=flask.session['end_date']).execute()
                for event in events['items']:
                    cont = False
                    if idlist:
                        for item in idlist:
                            if event['id'] == item:
                                cont = True
                    if cont:
                        continue
                    if 'dateTime' in event['start']:
                        eventStart = arrow.get(event['start']['dateTime'])
                        eventEnd = arrow.get(event['end']['dateTime'])
                    else:
                        eventStart = arrow.get(event['start']['date'])
                        eventEnd = arrow.get(event['end']['date'])
                    if eventStart < arrow.get(flask.session['end_date']):
                        if eventEnd > arrow.get(flask.session['begin_date']):
                            if 'transparency' in event:
                                continue
                            else:
                                eventDict = {
                                             'start':eventStart.format('YYYY-MM-DD HH:mm'),
                                             'end': eventEnd.format('YYYY-MM-DD HH:mm'),
                                             'event': event['summary'],
                                             'calendar': (service.calendars().get(calendarId = cal).execute())['summary'],
                                             'id':event['id']
                                            }
                                busyDict.append(eventDict)
                                cblockList.append(calendarBlock.make_calendarBlock(eventStart,eventEnd,event['summary'],(service.calendars().get(calendarId = cal).execute())['summary'],event['id']))
                                somelist.append(timeBlock.make_timeBlock(eventStart,eventEnd))
                page_token = events.get('nextPageToken')
                if not page_token:
                    break
        global CURRENT_BUSY_LIST
        CURRENT_BUSY_LIST = somelist
        iterateDate = arrow.get(flask.session['begin_date'])
        while iterateDate < arrow.get(flask.session['end_date']):
            tblockList.append(timeBlock.make_timeBlock(iterateDate, iterateDate.shift(minutes=+15)))
            iterateDate = iterateDate.shift(minutes=+15)
        userFreeTimes = []
        lastBlock = True
        tstart = None
    app.logger.debug("exited while loop")
    if busyDict:
        flask.g.busyTimes = busyDict
    if userFreeTimes:
        submitList = []
        for item in userFreeTimes:
            myDict = {
                'start':item.startTime.isoformat(),
                'end':item.endTime.isoformat()
            }
            submitList.append(myDict)
        flask.g.freeList = submitList
    return render_template('main.html')
@app.route("/choose")
def choose():
    ## We'll need authorization to list calendars
    ## I wanted to put what follows into a function, but had
    ## to pull it back here because the redirect has to be a
    ## 'return'
    app.logger.debug("Checking credentials for Google calendar access")
    credentials = valid_credentials()
    if not credentials:
      app.logger.debug("Redirecting to authorization")
      return flask.redirect(flask.url_for('oauth2callback'))

    gcal_service = get_gcal_service(credentials)
    app.logger.debug("Returned from get_gcal_service")
    flask.g.calendars = list_calendars(gcal_service)
    for cal in flask.g.calendars:
        app.logger.debug(cal)#need to see if there's an identifying variable
        #app.logger.debug(cal.events())
    #flask.g.busyTimes = None






    return render_template('main.html')
@app.route("/_userSubmit", methods=["POST"]):
    dbclient = MongoClient(MONGO_CLIENT_URL)
    db = getattr(dbclient, CONFIG.DB)
    collection = db.meets
    myObject = collection.find({"user_id":str(CURRENT_MEET_ID)}
    for item in CURRENT_BUSY_LIST:
        myObject['busy_list'].append(
        {
        "start":item.startTime.isoformat(),
        "end":item.endTime.isoformat()
        }
        )
    return render_template("user_end.html")

@app.route("/_doneBusy", methods=["POST"])
def _doneBusy():
    dbclient = MongoClient(MONGO_CLIENT_URL)
    db = getattr(dbclient, CONFIG.DB)
    collection = db.meets
    mylist = []
    for item in CURRENT_BUSY_LIST:
        mylist.append(
        {
        "start":item.startTime.isoformat(),
        "end":item.endTime.isoformat()
        }
        )
    collection.insert(
    {
    "admin_id":ADMIN_ID,
    "user_id":CURRENT_MEET_ID,
    "busy_list":mylist
    }
    )
    flask.g.eventlist = mylist
    return render_template("endscreen.html")
@app.route("/_select", methods=["POST"])
def _select():
    app.logger.debug("Selecting calendar")
    calendarIDList=flask.request.form.getlist("calendar")
    global calendar
    service = get_gcal_service(valid_credentials())
    #for cal in calendars = service.calendars().get(calendarId = calendarID).execute():
    #    calendar.append(cal)
    #an array
    for ID in calendarIDList:
        calendar.append(ID)
    flask.g.busyTimes = None
    return flask.redirect(flask.url_for('main'))

@app.route("/_getData", methods=["POST"])
def _getData():
    app.logger.debug("User inputting meeting data")
    global CURRENT_MEET_ID
    CURRENT_MEET_ID = flask.request.forms.get("meetID")
    return render_template("main2.html")
@app.route("/_deleteBusy", methods=["POST"])
def _deleteBusy():
    app.logger.debug("Deleting certain busy items")
    busyIDlist=flask.request.form.getlist("busy")
    global idlist
    for ID in busyIDlist:
        if ID not in idlist:
            idlist.append(ID)
    return flask.redirect(flask.url_for('main'))

@app.route("/_adminLOGIN", methods=["POST"])
def _adminLogin():
    app.logger.debug("Admin logging in")
    dbclient = MongoClient(MONGO_CLIENT_URL)
    db = getattr(dbclient, CONFIG.DB)
    collection = db.meets
    yourData = collection.find({"admin_id":str(flask.request.form.get("adminID"))})
    flask.g.eventlist = yourData['busy_list']
    return render_template("endscreen")

@app.route("/_newScheduler", methods=["POST"])
def _newScheduler():
    #this is the 'admin' user
    app.logger.debug("Creating new meeting scheduler")
    random = randint(0,999999999999)
    random2 = randint(0,999999999999)
    flask.g.meet = random
    CURRENT_MEET_ID = random
    global ADMIN_ID
    ADMIN_ID = random2
    flask.g.admin = random2
    return render_template("displayMeetID.html")

@app.route("/_gotoMain", methods=["POST"])
def _gotoMain():
    app.logger.debug("Entering gotoMain")
    global CURRENT_MEET_ID
    CURRENT_MEET_ID = flask.request.form.get("meetID")
    return render_template("main.html")

####
#
#  Google calendar authorization:
#      Returns us to the main /choose screen after inserting
#      the calendar_service object in the session state.  May
#      redirect to OAuth server first, and may take multiple
#      trips through the oauth2 callback function.
#
#  Protocol for use ON EACH REQUEST:
#     First, check for valid credentials
#     If we don't have valid credentials
#         Get credentials (jump to the oauth2 protocol)
#         (redirects back to /choose, this time with credentials)
#     If we do have valid credentials
#         Get the service object
#
#  The final result of successful authorization is a 'service'
#  object.  We use a 'service' object to actually retrieve data
#  from the Google services. Service objects are NOT serializable ---
#  we can't stash one in a cookie.  Instead, on each request we
#  get a fresh serivce object from our credentials, which are
#  serializable.
#
#  Note that after authorization we always redirect to /choose;
#  If this is unsatisfactory, we'll need a session variable to use
#  as a 'continuation' or 'return address' to use instead.
#
####

def valid_credentials():
    """
    Returns OAuth2 credentials if we have valid
    credentials in the session.  This is a 'truthy' value.
    Return None if we don't have credentials, or if they
    have expired or are otherwise invalid.  This is a 'falsy' value.
    """
    if 'credentials' not in flask.session:
      return None

    credentials = client.OAuth2Credentials.from_json(
        flask.session['credentials'])

    if (credentials.invalid or
        credentials.access_token_expired):
      return None
    return credentials


def get_gcal_service(credentials):
  """
  We need a Google calendar 'service' object to obtain
  list of calendars, busy times, etc.  This requires
  authorization. If authorization is already in effect,
  we'll just return with the authorization. Otherwise,
  control flow will be interrupted by authorization, and we'll
  end up redirected back to /choose *without a service object*.
  Then the second call will succeed without additional authorization.
  """
  if credentials == None:
      return flask.redirect(flask.url_for('index'))
  app.logger.debug("Entering get_gcal_service")
  http_auth = credentials.authorize(httplib2.Http())
  service = discovery.build('calendar', 'v3', http=http_auth)
  app.logger.debug("Returning service")
  return service

@app.route('/oauth2callback')
def oauth2callback():
  """
  The 'flow' has this one place to call back to.  We'll enter here
  more than once as steps in the flow are completed, and need to keep
  track of how far we've gotten. The first time we'll do the first
  step, the second time we'll skip the first step and do the second,
  and so on.
  """
  app.logger.debug("Entering oauth2callback")
  flow =  client.flow_from_clientsecrets(
      CLIENT_SECRET_FILE,
      scope= SCOPES,
      redirect_uri=flask.url_for('oauth2callback', _external=True))
  ## Note we are *not* redirecting above.  We are noting *where*
  ## we will redirect to, which is this function.

  ## The *second* time we enter here, it's a callback
  ## with 'code' set in the URL parameter.  If we don't
  ## see that, it must be the first time through, so we
  ## need to do step 1.
  app.logger.debug("Got flow")
  if 'code' not in flask.request.args:
    app.logger.debug("Code not in flask.request.args")
    auth_uri = flow.step1_get_authorize_url()
    return flask.redirect(auth_uri)
    ## This will redirect back here, but the second time through
    ## we'll have the 'code' parameter set
  else:
    ## It's the second time through ... we can tell because
    ## we got the 'code' argument in the URL.
    app.logger.debug("Code was in flask.request.args")
    auth_code = flask.request.args.get('code')
    credentials = flow.step2_exchange(auth_code)
    flask.session['credentials'] = credentials.to_json()
    ## Now I can build the service and execute the query,
    ## but for the moment I'll just log it and go back to
    ## the main screen
    app.logger.debug("Got credentials")
    return flask.redirect(flask.url_for('choose'))

#####
#
#  Option setting:  Buttons or forms that add some
#     information into session state.  Don't do the
#     computation here; use of the information might
#     depend on what other information we have.
#   Setting an option sends us back to the main display
#      page, where we may put the new information to use.
#
#####

@app.route('/setrange', methods=['POST'])
def setrange():
    """
    User chose a date range with the bootstrap daterange
    widget.
    """
    app.logger.debug("Entering setrange")
    flask.flash("Setrange gave us '{}'".format(
      request.form.get('daterange')))
    daterange = request.form.get('daterange')
    flask.session['daterange'] = daterange
    daterange_parts = daterange.split()
    flask.session['begin_date'] = interpret_date(daterange_parts[0])
    flask.session['end_date'] = interpret_date(daterange_parts[2])
    app.logger.debug("Setrange parsed {} - {}  dates as {} - {}".format(
      daterange_parts[0], daterange_parts[1],
      flask.session['begin_date'], flask.session['end_date']))
    return flask.redirect(flask.url_for("choose"))

####
#
#   Initialize session variables
#
####

def init_session_values():
    """
    Start with some reasonable defaults for date and time ranges.
    Note this must be run in app context ... can't call from main.
    """
    # Default date span = tomorrow to 1 week from now
    now = arrow.now('local')     # We really should be using tz from browser
    tomorrow = now.replace(days=+1)
    nextweek = now.replace(days=+7)
    flask.session["begin_date"] = tomorrow.floor('day').isoformat()
    flask.session["end_date"] = nextweek.ceil('day').isoformat()
    flask.session["daterange"] = "{} - {}".format(
        tomorrow.format("MM/DD/YYYY"),
        nextweek.format("MM/DD/YYYY"))
    # Default time span each day, 8 to 5
    flask.session["begin_time"] = interpret_time("9am")
    flask.session["end_time"] = interpret_time("5pm")

def interpret_time( text ):
    """
    Read time in a human-compatible format and
    interpret as ISO format with local timezone.
    May throw exception if time can't be interpreted. In that
    case it will also flash a message explaining accepted formats.
    """
    app.logger.debug("Decoding time '{}'".format(text))
    time_formats = ["ha", "h:mma",  "h:mm a", "H:mm"]
    try:
        as_arrow = arrow.get(text, time_formats).replace(tzinfo=tz.tzlocal())
        as_arrow = as_arrow.replace(year=2016) #HACK see below
        app.logger.debug("Succeeded interpreting time")
    except:
        app.logger.debug("Failed to interpret time")
        flask.flash("Time '{}' didn't match accepted formats 13:30 or 1:30pm"
              .format(text))
        raise
    return as_arrow.isoformat()
    #HACK #Workaround
    # isoformat() on raspberry Pi does not work for some dates
    # far from now.  It will fail with an overflow from time stamp out
    # of range while checking for daylight savings time.  Workaround is
    # to force the date-time combination into the year 2016, which seems to
    # get the timestamp into a reasonable range. This workaround should be
    # removed when Arrow or Dateutil.tz is fixed.
    # FIXME: Remove the workaround when arrow is fixed (but only after testing
    # on raspberry Pi --- failure is likely due to 32-bit integers on that platform)


def interpret_date( text ):
    """
    Convert text of date to ISO format used internally,
    with the local time zone.
    """
    try:
      as_arrow = arrow.get(text, "MM/DD/YYYY").replace(
          tzinfo=tz.tzlocal())
    except:
        flask.flash("Date '{}' didn't fit expected format 12/31/2001")
        raise
    return as_arrow.isoformat()

def next_day(isotext):
    """
    ISO date + 1 day (used in query to Google calendar)
    """
    as_arrow = arrow.get(isotext)
    return as_arrow.replace(days=+1).isoformat()

####
#
#  Functions (NOT pages) that return some information
#
####

def list_calendars(service):
    """
    Given a google 'service' object, return a list of
    calendars.  Each calendar is represented by a dict.
    The returned list is sorted to have
    the primary calendar first, and selected (that is, displayed in
    Google Calendars web app) calendars before unselected calendars.
    """
    app.logger.debug("Entering list_calendars")
    calendar_list = service.calendarList().list().execute()["items"]
    result = [ ]
    for cal in calendar_list:
        kind = cal["kind"]
        id = cal["id"]
        if "description" in cal:
            desc = cal["description"]
        else:
            desc = "(no description)"
        summary = cal["summary"]
        # Optional binary attributes with False as default
        selected = ("selected" in cal) and cal["selected"]
        primary = ("primary" in cal) and cal["primary"]


        result.append(
          { "kind": kind,
            "id": id,
            "summary": summary,
            "selected": selected,
            "primary": primary
            })
    return sorted(result, key=cal_sort_key)


def cal_sort_key( cal ):
    """
    Sort key for the list of calendars:  primary calendar first,
    then other selected calendars, then unselected calendars.
    (" " sorts before "X", and tuples are compared piecewise)
    """
    if cal["selected"]:
       selected_key = " "
    else:
       selected_key = "X"
    if cal["primary"]:
       primary_key = " "
    else:
       primary_key = "X"
    return (primary_key, selected_key, cal["summary"])


#################
#
# Functions used within the templates
#
#################

@app.template_filter( 'fmtdate' )
def format_arrow_date( date ):
    try:
        normal = arrow.get( date )
        return normal.format("ddd MM/DD/YYYY")
    except:
        return "(bad date)"

@app.template_filter( 'fmttime' )
def format_arrow_time( time ):
    try:
        normal = arrow.get( time )
        return normal.format("HH:mm")
    except:
        return "(bad time)"

#############


if __name__ == "__main__":
  # App is created above so that it will
  # exist whether this is 'main' or not
  # (e.g., if we are running under green unicorn)
  app.run(port=CONFIG.PORT,host="0.0.0.0")
