import os
import time
import datetime
import ConfigParser
import sys
from slackclient import SlackClient
import database
import requests
from math import floor

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




def floored_percentage(val, digits):
    val *= 10 ** (digits + 2)
    return '{1:.{0}f}%'.format(digits, floor(val) / 10 ** digits)


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
        return -9999 # error code

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
                            select p.user_id, p.coin_type, sal.sold, sum(p.amount) as purchased, sal.usd_gained, sum(p.usd) as usd_spent,  sum(p.amount) - sal.sold as balance, 0.0 as current_worth from
                            (select s.user_id, s.coin_type, sum(s.amount) as sold, sum(s.usd) as usd_gained
                            from transactions s
                            where s.user_id = %s and s.type = "sale"
                            group by s.user_id, s.coin_type) as sal

                            right outer join transactions p on sal.user_id = p.user_id and sal.coin_type = p.coin_type
                            where p.user_id = %s and p.type = "purchase"
                            group by p.user_id, p.coin_type
                        """,[user, user])

    # clean records.  Replace nulls with 0
    for record in records :
        if record['sold'] is None:
            record['sold'] = 0
            record['balance'] = record['purchased']
            record['usd_gained'] = 0

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
    # find proper source for the coin
    db = database.Database()
    coins = db.fetchAll("""select source from supported_coins where coin_id = %s""",[type.upper()])
    db.close()

    if coins[0]['source'] == "coinbase":
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
    db = database.Database()
    if type  == "purchase" :
        records = db.fetchAll("""select * from purchases where record_complete = 0 and last_updated > now() - interval 30 minute and user_id = %s""",[user])

    elif type == "sale" :
        records = db.fetchAll("""select * from sales where record_complete = 0 and last_updated > now() - interval 30 minute and user_id = %s""",[user])
        
    if len(records) > 0 :
        return True
    db.close()


    return False


# called on a scheduled task to log current rates and values of wallets
def log_performance():
    # get a list of users on the server
    db = database.Database()
    users = db.fetchAll("select distinct user_id from purchases where record_complete = 1 group by user_id")

    # fetch supported coins
    coins = db.fetchAll("select * from supported_coins")
    #fetch current rates for the coins and record the rates
    for coin in coins :
        current_price = get_current_price(coin['coin_id'].lower())
        db.execute("""insert into price_history(date, coin, price) values(now(),%s,%s)""",[coin['coin_id'],current_price])


    # for each user, get the balance
    for user in users:
        # get wallet balances
        wallets = wallet_ballance(user["user_id"])

        total_spent = 0
        total_value = 0

        # for each coin type, fetch the value and aggregate it
        for wallet in wallets:
            current_price = db.fetchAll("""select * from price_history where coin = %s order by date desc limit 1""",[wallet['coin_type'].upper()])

            total_spent = total_spent + wallet['usd_spent']
            total_value = total_value + (wallet['balance'] * current_price[0]['price'])
  
        
        #write the record
        db.runSql("""insert into performance_log (user_id,date,total_spent, total_value) values(%s,now(),%s,%s)
                    """,[user["user_id"],total_spent,round(total_value,2)])

    log_event("Performance logged")
    db.close()


if __name__ == "__main__": #to depricate
    arguments = sys.argv[1:]

    
        
   