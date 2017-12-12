
import os
import time
import datetime
import ConfigParser
import sys
from slackclient import SlackClient
import bot_utilities
import database
import bot_commands


# get config
myPath = os.path.dirname(os.path.abspath(__file__))


try: 
    config = ConfigParser.ConfigParser()
    config.read(myPath+"\config.ini")
    token = config.get('config','key')
    BOT_ID = config.get('config','bot_id')
    log_chat = config.get('config','log_chat')
    admin_user = config.get('config','admin')
    


    print("config loaded \n")

except:
    print ("Error reading the config file")

slack_client = SlackClient(token)
AT_BOT = "<@" + BOT_ID + ">"




#handle the responses
def handle_command(command, channel, user,command_orig):
    """
        Receives commands directed at the bot and determines if they
        are valid commands. If so, then acts on the commands. If not,
        returns back what it needs for clarification.
    """
    db = database.Database()
    response = "Sorry, I'm kind of a dumb robot.  I have no idea what you mean. Type 'help' to learn about me"
    deffered = False
    
    if command.startswith('hi') or command.startswith('hello'):
        response = "well hello there!"
        
    # user wants to know possible commands
    elif command.startswith('help') : 
        response = """
You can use the following commands:\n
_______\n
*HOW AM I DOING?*: tells you your current crypto profit\n
*WHAT'S MY BALANCE?*: lists your current crypto balance\n
*I BOUGHT ___*: tell me when you buy crypto\n
*I SOLD ___*: tell me when you sell crypto\n
*SHOW MY TRANSACTIONS*: lists your transactions\n
*DELETE PURCHASE #*: deletes indicated purchase transaction\n
*DELETE SALE #*: deletes indicated sale transaction\n
 \n
_tip: if you need to remove coin due to fees, log a sale for $0_\n
_______\n
                    """
    
    elif command.startswith('how am i doing') :
        bot_commands.provide_profit_info(user,channel,command)
        deffered = True

    elif 'balance' in command :
        bot_commands.whats_balance(user,channel,command)
        deffered = True

    elif command.startswith('i bought') :
        bot_commands.add_purchase(user,channel,command)
        deffered = True

    elif command.startswith('i sold') :
        bot_commands.add_sale(user,channel,command)
        deffered = True

    elif ('show' in command or 'list' in command) and 'transaction' in command :
        bot_commands.list_transactions(user,channel,command)
        deffered = True


    elif command.startswith('delete purchase') :
        bot_commands.delete_transaction(user,channel,command,"purchase")
        deffered = True

    elif command.startswith('delete sale') :
        bot_commands.delete_transaction(user,channel,command,"sale")
        deffered = True

    elif command.startswith("go kill yourself") and user == admin_user :
        bot_utilities.log_event("self destruct activated")
        slack_client.api_call("chat.postMessage", channel=channel, text="wow, that's rude", as_user=True)
        sys.exit()


    elif bot_utilities.user_is_adding_record(user, "purchase") : # determine if the user is currently working to create a purchase record
        bot_commands.handle_ongoing_record_creation(user,channel,command,"purchase")
        deffered = True

    elif bot_utilities.user_is_adding_record(user, "sale") : # determine if the user is currently working to create a sale record
        bot_commands.handle_ongoing_record_creation(user,channel,command,"sale")
        deffered = True

    if deffered == False :
        slack_client.api_call("chat.postMessage", channel=channel,
                            text=response, as_user=True)
    db.close()


def parse_slack_output(slack_rtm_output):
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    try :
        output_list = slack_rtm_output
        if output_list and len(output_list) > 0:
            for output in output_list:
                #print ("\n")
                #print(output)
                #print ("\n")

                try : # ensure the message has a user and text
                    text = output['text']
                    user = output['user']
                except:
                    return None,None,None,None
            

                if output and 'text' in output and AT_BOT in output['text']:
                    # return text after the @ mention, whitespace removed
                    output['text'] = output['text'].replace(u"\u2019", '\'')
                    return output['text'].split(AT_BOT)[1].strip().lower(), \
                           output['channel'], \
                           output['user'], \
                           output['text'].split(AT_BOT)[1].strip()
            
                #handle im conversations without needing @
                elif output and 'text' in output and output['user'] != BOT_ID and output['user'] != "USLACKBOT":
                    output['text'] = output['text'].replace(u"\u2019", '\'')
                

                    response = slack_client.api_call("im.list")
                    ims = response["ims"]
                    for im in ims :
                        if im["id"] == output['channel']:
                            return output['text'].lower(), \
                                   output['channel'], \
                                   output['user'], \
                                   output['text']
        return None, None, None, None

    except : # nested tries to prevent the bot from crashing
        bot_utilities.log_event("An unhandled error was encountered - parse_slack_output")
        try: 
            bot_utilities.log_event(output['channel']+" " + output['user'])
            return None, None, None, None
        except :
            bot_utilities.log_event("failed to log the unhandled error")
            return None, None, None, None


if __name__ == "__main__":
    READ_WEBSOCKET_DELAY = 1 # 1 second delay between reading from firehose 

    if slack_client.rtm_connect():
        bot_utilities.log_event("Bitcoin Bot connected and running!")
        while True:
            command, channel, user, command_orig = parse_slack_output(slack_client.rtm_read())
            if command and channel:
                handle_command(command, channel, user, command_orig)        

            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        bot_utilities.log_event("Connection failed. Invalid Slack token or bot ID?")

# use this to get your bot ID for the config file

#BOT_NAME = 'og_bot'
#
#if __name__ == "__main__":
#    api_call = slack_client.api_call("users.list")
#    if api_call.get('ok'):
#        # retrieve all users so we can find our bot
#        users = api_call.get('members')
#        for user in users:
#            if 'name' in user and user.get('name') == BOT_NAME:
#                print("Bot ID for '" + user['name'] + "' is " + user.get('id'))
#    else:
#        print("could not find bot user with the name " + BOT_NAME)