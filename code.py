import time
import adafruit_requests
import adafruit_portalbase
from adafruit_datetime import date, datetime, time as dtttime, timezone
import wifi
import socketpool
import ssl
import board
import alarm
import struct
import displayio

from adafruit_magtag.magtag import MagTag
from adafruit_magtag.graphics import Graphics

# Press A to cycle through tweeters, press D to cycle through tweets

magtag = MagTag(debug=True)
max_tweet_no = 9 # how many tweets to cycle through on button press. is 0-based and would need a diff api req if we're gonna go above 9 i think
user_handles = ['WTMMP','dril']
wait_time_on_err_seconds = 5 * 60
wait_time_refresh_seconds = 20 * 60

try:
    from secrets import secrets
except ImportError:
    print(
        """WiFi settings are kept in secrets.py, please add them there!
the secrets dictionary must contain 'ssid' and 'password' at a minimum"""
    )
    raise

bearer_token = secrets["twitter_bearer_token"]

#wifi = adafruit_portalbase.wifi_esp32s2.WiFi()
base = adafruit_portalbase.network.NetworkBase(wifi)

wifi.radio.connect(secrets["ssid"], secrets["password"])

pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool, ssl.create_default_context())

def generic_fetch(url):
    #print(url)
    return requests.get(url,
                      headers={"Authorization": "Bearer " + bearer_token},
                      ).json()

def get_user_id(handle=None):
    j = generic_fetch(f'https://api.twitter.com/2/users/by/username/{handle}')
    user_id = j['data']['id']
    display_name = j['data']['name']
    return user_id, display_name

def get_tweet_id_and_text(user_id, tweet_no):
    j = generic_fetch(f'https://api.twitter.com/2/users/{user_id}/tweets?exclude=replies,retweets&tweet.fields=created_at')
    timestamps = [x['created_at'] for x in j['data']]
    #print(f"timestamps is {timestamps}")
    timestamps.sort(reverse=True)
    #print(f"timestamps, now sorted, is {timestamps}")
    timestamp_to_ret = timestamps[tweet_no]
    #print(f"timestamp_to_ret is {timestamp_to_ret}")
    tweet = [x for x in j['data'] if x['created_at'] == timestamp_to_ret][0]
    tweet = j['data'][tweet_no]
    tweet_id = tweet['id']
    text = tweet['text']
    return tweet_id, text, timestamp_to_ret

def get_tweet_timestamp(tweet_id): # DEPRECATED
    j = generic_fetch(f'https://api.twitter.com/2/tweets/{tweet_id}?tweet.fields=created_at')
    return j['data']['created_at']

wake_alarm = alarm.wake_alarm
alert_if_diff_tweet_id = False

if wake_alarm is None: # initialize tweet_no on first run
    print("wake_alarm was none")
    tweet_no = 0
    user_handle_ix = 0
    user_handle = user_handles[user_handle_ix]
    alarm.sleep_memory[0] = tweet_no
    alarm.sleep_memory[1] = user_handle_ix
    #magtag.add_text(text=f"wakealarm none",
    #    text_wrap=30,
    #    text_maxlen=160,
    #    text_scale=0.05,
    #    text_position=(
    #        (magtag.graphics.display.width),
    #        10,
    #    ),
    #    text_anchor_point=(1,0),
    #    line_spacing=0.75)

else:
    if isinstance(wake_alarm, alarm.time.TimeAlarm): # recall tweet_no # this test isn't working
        print("wake_alarm was TimeAlarm")
        tweet_no = alarm.sleep_memory[0]
        user_handle_ix = alarm.sleep_memory[1]
        last_tweet_id_residual = alarm.sleep_memory[2]
        alert_if_diff_tweet_id = True
        user_handle = user_handles[user_handle_ix]
        #magtag.add_text(text=f"wake_alarm was TimeAlarm",
        #    text_wrap=30,
        #    text_maxlen=160,
        #    text_scale=0.05,
        #    text_position=(
        #        (magtag.graphics.display.width),
        #        (magtag.graphics.display.height)-12,
        #    ),
        #    text_anchor_point=(1,1),
        #    line_spacing=0.75)

    else:
        print("wake_alarm was a button")
        print(f"wake alarm pin: {wake_alarm.pin}")
        #magtag.add_text(text=f"wake alarm pin: {wake_alarm.pin}",
        #    text_wrap=30,
        #    text_maxlen=160,
        #    text_scale=0.05,
        #    text_position=(
         #       (magtag.graphics.display.width),
         #       (magtag.graphics.display.height)-12,
         #   ),
         #   text_anchor_point=(1,1),
         #   line_spacing=0.75)

        # use button A to toggle tweeters, use button D to toggle tweets
        if wake_alarm.pin == board.BUTTON_D:
            tweet_no = alarm.sleep_memory[0] + 1
            if tweet_no > max_tweet_no: # wrap around tweet numbers
                tweet_no = 0
            alarm.sleep_memory[0] = tweet_no
            user_handle_ix = alarm.sleep_memory[1]
            user_handle = user_handles[user_handle_ix]
        else: # toggle tweeters
            tweet_no = 0 # always go to the first tweet of a new tweeter
            user_handle_ix = alarm.sleep_memory[1] + 1
            if user_handle_ix >= len(user_handles): # wrap around tweet numbers
                user_handle_ix = 0
            alarm.sleep_memory[1] = user_handle_ix
            user_handle = user_handles[user_handle_ix]



print(f"tweet_no is {tweet_no}")

try:
    user_id, display_name = get_user_id(handle=user_handle)
    tweet_id, tweet_text, tweet_timestamp = get_tweet_id_and_text(user_id, tweet_no)
    print(tweet_text)
    print(tweet_id)
    #tweet_timestamp = get_tweet_timestamp(tweet_id) # now gotten in the other req
    if alert_if_diff_tweet_id and int(tweet_id) % (2**7) != last_tweet_id_residual:
        magtag.peripherals.neopixel_disable = False
        magtag.peripherals.neopixels.fill((255,255,255))
    last_tweet_id = int(tweet_id)
    alarm.sleep_memory[2] = last_tweet_id % (2**7)
except Exception as e:
    magtag.add_text(text="pulling data failed, trying again in 5 min, error was " + str(e),
                    text_position=(10, 20),
                    text_wrap=40)
    print(f"pulling data failed, trying again in {wait_time_on_err_seconds/60} min, error was " + str(e))
    raise
    magtag.exit_and_deep_sleep(wait_time_on_err_seconds)


print(tweet_timestamp)
if user_handle[0] != "@":
    user_handle = "@" + user_handle
"""
dtstr = ''
timestr = ''
before_t = True
for char in tweet_timestamp:
    if char == 'T':
        before_t = False
        continue
    if before_t:
        dtstr += char
    elif char != 'Z':
        timestr += char
print(dtstr)
print(timestr)
t = dtttime.fromisoformat(timestr)
t.tzinfo = 0
print(t.tzname())
d = date.fromisoformat(dtstr)
dt = datetime.combine(d,t)
print(dt)
"""
#ts_nice = datetime.fromisoformat(tweet_timestamp)
#print(str(ts_nice))

# Display setup
magtag.set_background("/images/background.bmp")

# Twitter name
magtag.add_text(
    text_position=(60, 10),
    text_font="/fonts/Arial-Bold-12.pcf"
)

# Twitter handle (@username)
magtag.add_text(
    text_position=(60, 28),
    text_font="/fonts/Arial-12.bdf",
    #text_transform=lambda x: "@%s" % x
)

# Tweet text
magtag.add_text(
    text_font="/fonts/helvB12.pcf",
    text_wrap=47,
    text_maxlen=300,
    text_position=(
        5,
        (magtag.graphics.display.height // 2) + 13,
    ),
    #line_spacing=0.75
    line_spacing=1 # use line_spacing=1 for default font
)

# timestamp at bottom
magtag.add_text(
    #text_font="/fonts/Arial-12.bdf",
    text_wrap=30,
    text_maxlen=160,
    text_scale=0.05,
    text_position=(
        (magtag.graphics.display.width),
        (magtag.graphics.display.height),
    ),
    text_anchor_point=(1,1),
    line_spacing=0.75
)
magtag.set_text(display_name, 0, auto_refresh=False)
magtag.set_text(user_handle, 1, auto_refresh=False)
magtag.set_text(tweet_text, 2, auto_refresh=False)
magtag.set_text(tweet_timestamp, 3)

time_alarm = alarm.time.TimeAlarm(epoch_time=time.time()+wait_time_refresh_seconds)
magtag.peripherals.deinit()
buttons = (board.BUTTON_A, board.BUTTON_D)  # can only take 2 buttons
alarms = [alarm.pin.PinAlarm(pin=pin, value=False, pull=True) for pin in buttons]
alarms += [time_alarm]
print("test")

alarm.exit_and_deep_sleep_until_alarms(*alarms)

#magtag.exit_and_deep_sleep(60*60)
