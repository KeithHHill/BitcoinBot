import os
import time
import datetime
import ConfigParser
import sys
from slackclient import SlackClient
import database
import requests

# get config
myPath = os.path.dirname(os.path.abspath(__file__))

try: 
    config = ConfigParser.ConfigParser()
    config.read(myPath+"\config.ini")
    token = config.get('config','key')
    BOT_ID = config.get('config','bot_id')
    log_chat = config.get('config','log_chat')

   
except:
    print ("Error reading the config file-bot utilities")

slack_client = SlackClient(token)





# logs a message to the bot log channel
def log_event(message) :
    try :
        print(message)
        slack_client.api_call("chat.postMessage", channel=log_chat,text=message, as_user=True)
    except :
        print("error logging")


# posts text to a specified channel
def post_to_channel(channel,text):
    try:
        slack_client.api_call("chat.postMessage", channel=channel,text=text, as_user=True)
    except :
        log_event("failed to post to channel: " + str(channel) + ": " + str(text))


# bot sends a private message to the user (used in non solicited messages)
def send_private_message(user, message) :
    # create channel
    call = "im.open?user="+user
    response = slack_client.api_call(call)

    slack_client.api_call("chat.postMessage", channel=response['channel']['id'], text=message, as_user=True)


# returns true if the incomming channel is an IM
def is_private_conversation(channel):
    response = slack_client.api_call("conversations.info?channel="+channel)
    if response['channel']['is_im'] == False:
        return False
    else :
        return True


# get's the user's name in slack
def get_slack_name(user_id) :
    call = "users.info?user="+user_id
    response = slack_client.api_call(call)
    slack_name = response['user']['name']
    if response['user']['profile']['display_name'] != "" :
        slack_name = response['user']['profile']['display_name']

    return slack_name


# checks to see if there has been a name update
def update_name(user_id,current_name) :
    db = database.Database()

    call = "users.info?user="+user_id
    response = slack_client.api_call(call)
    slack_name = response['user']['name']
    if response['user']['profile']['display_name'] != "" :
        slack_name = response['user']['profile']['display_name']
    if current_name != slack_name :
        # alert general chat as well as the log
        message = "user "+current_name+" has changed their name in slack and is now known as "+slack_name
        log_event(message)
        db.runSql("update member_orientation set member_name =%s where member_id = %s",[slack_name,user_id])
        slack_client.api_call("chat.postMessage", channel=general_chat.upper(), 
                              text=message, as_user=True)

    db.close()



# tries to find a number in the command and returns it
def parse_number_from_command(command):
    str_cmd = str(command)
    try :
        num_found = float(''.join([c for c in str_cmd if c in '.0123456789']))
    except :
        return 0

    return num_found





# returns true if the user is active in slack
def user_is_active(user):
    response = slack_client.api_call("users.info",user = user)

    if response['ok'] == True :
        if response['user']['deleted'] == True :
            return False
        else : 
            return True
    else :
        return False



def wallet_ballance(user) :
    db = database.Database()
    records = db.fetchAll("""
                            select user_id, coin_type, sum(amount) as purchased, sum(usd_spent) as usd_spent
                            from purchases
                            where user_id = %s
                            group by user_id, coin_type
                        """,[user])

    return records

# gets json from the requested url
def getPage(url, proxies=''):
    try:
        return request(url, proxies)
    except:
        return request(url, proxies) #Retry

def request(url, proxies=''):
    reqHeaders = {'User-Agent' : 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.101 Safari/537.36',
                  #'X-API-Key': 'c18b20ce8a54453c96d962e2e639f4b0'
                  }
    
    page = requests.get(url, headers = reqHeaders, proxies=proxies, timeout=45)
    
    try: 
        data = page.json()
    except :
        return None

    return data


def get_current_price(type = "btc") :
    response = request("https://api.coinbase.com/v2/prices/"+ type+"-USD/spot")
    
    try:
        curPrice = response["data"]["amount"]
       
        curPrice = float(curPrice) #convert to number

        return curPrice

    except :
        log_event("attempted to get the current Coinbase price and failed to get a response")
        return 0

    return 0

# expects a type in the request and if the user is currently adding a record, return true
def user_is_adding_record(user, type) :
    if type == 'purchase' :
        db = database.Database()
        if type  == "purchase" :
            records = db.fetchAll("""select * from purchases where record_complete = 0 and last_updated > now() - interval 30 minute and user_id = %s""",[user])

        
        if len(records) > 0 :
            return True
        db.close()

    return False


if __name__ == "__main__": #to depricate
    arguments = sys.argv[1:]

    
        
   