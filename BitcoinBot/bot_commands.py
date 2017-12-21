
import os
import time
import datetime
import ConfigParser
import sys
from slackclient import SlackClient
import bot_utilities
import database
import requests
import json
from decimal import Decimal


# get config
myPath = os.path.dirname(os.path.abspath(__file__))


try: 
    config = ConfigParser.ConfigParser()
    config.read(myPath+"\config.ini")
    token = config.get('config','key')
    BOT_ID = config.get('config','bot_id')
    log_chat = config.get('config','log_chat')
    admin_user = config.get('config','admin')
    

except:
    print ("Error reading the config file - bot commands")


# lists the user's current wallets
def whats_balance(user,channel,command) :
    response = "something went wrong - balance"
    wallets = bot_utilities.wallet_ballance(user)

    response = "Wallets:\n"
    for wallet in wallets :
        current_value = bot_utilities.get_current_price(wallet["coin_type"]) * float(wallet["balance"])
        response = response + "*"+ wallet["coin_type"].upper() + ":* " + str(round(wallet["balance"],8)) + " _($" + str(round(current_value,2))+")_\n"

    bot_utilities.log_event(user + " requested wallet balances: " + command)
    bot_utilities.post_to_channel(channel,response)


# lets a user delete their own transaction
def delete_transaction(user,channel,command, type = "purchase") :
    response= "something went wrong - delete_transaction"

    # make sure we have a number in the command
    trans_number = bot_utilities.parse_number_from_command(command)

    if trans_number == -9999 :
        response = "You need to give me a transaction number.  \"List Transactions\" will show you a list of your transactions."
        bot_utilities.log_event(user + " attempted to delete a transaction but provided no transaction number: " + command)

    else : # we have a transaction
        db = database.Database()
        if type == "purchase" :
            records = db.fetchAll("""select * from purchases where purchase_id = %s and user_id = %s""",[trans_number,user])

            # verify that we have a record
            if len(records) == 0 :
                response = "You need to give me a valid transaction number.  \"List Transactions\" will show you a list of your transactions."
                bot_utilities.log_event(user + " attempted to delete a transaction but provided an invalid transaction number: " + command)

            else : # delete the record
                db.runSql("""delete from purchases where purchase_id = %s""",[records[0]["purchase_id"]])
                response = "Alright, that record has been deleted."
                bot_utilities.log_event(user + " has deleted a transaction: " + command)
       


        else : # type is sale
            records = db.fetchAll("""select * from sales where purchase_id = %s and user_id = %s""",[trans_number,user])

            # verify that we have a record
            if len(records) == 0 :
                response = "You need to give me a valid transaction number.  \"List Transactions\" will show you a list of your transactions."
                bot_utilities.log_event(user + " attempted to delete a transaction but provided an invalid transaction number: " + command)

            else : # delete the record
                db.runSql("""delete from sales where purchase_id = %s""",[records[0]["purchase_id"]])
                response = "Alright, that record has been deleted."
                bot_utilities.log_event(user + " has deleted a transaction: " + command)

        db.close()
    bot_utilities.post_to_channel(channel,response)


# returns a list of the user's transactions
def list_transactions(user,channel,command) :
    response = "something went wrong - list_transactions"

    db = database.Database()
    records = db.fetchAll("""
                            select *, "purchase" as type 
                            from purchases 
                            where user_id = %s and record_complete = 1

                            union

                            select * , "sale" as type
                            from sales 
                            where user_id = %s and record_complete = 1
                            """,[user, user])
    db.close()

    response = "ID | trans | coin | amount | USD | date \n"

    for record in records :
        response = response + str(record["purchase_id"]) + " | " + record["type"] + " | " + record["coin_type"].upper() + " | " + str(record["amount"]) + " | $" + str(record["usd_spent"]) + " | " + str(record["date"]) + "\n"

    bot_utilities.post_to_channel(channel,response)
    bot_utilities.log_event(user + " listed transactions")


# user asks how their investment is doing
def provide_profit_info(user,channel,command):
    response = "something went wrong - provide_profit_info"
    
    # get the user's current ballance
    wallets = bot_utilities.wallet_ballance(user)

    db = database.Database()
    # get supported coins
    coins = db.fetchAll("select *, 0.0 as current_value, 0.0 as current_worth from supported_coins")


    # find the current rates
    for coin in coins :
        coin['current_value'] = Decimal(bot_utilities.get_current_price(coin['coin_id'].lower()))


    total_spent = 0
    total_worth = 0

    # match the wallets with the coins and populate the current worth
    for wallet in wallets:
        for coin in coins :
            if wallet["coin_type"].lower() == coin["coin_id"].lower():
                wallet["current_worth"] = wallet["balance"] * coin["current_value"]
                break
        #sum total spent and worth
        total_spent = total_spent + wallet["usd_spent"]
        total_worth = total_worth + wallet["current_worth"]
  
    total_worth = round(total_worth,2)
    total_change = total_worth-float(total_spent)  # worth-spent

    
    # fetch the values to compare to day/month
    day_record = db.fetchAll("""select user_id, total_spent, total_value 
                                from performance_log 
                                where user_id = %s and date > now() - interval 24 hour
                                order by date asc limit 1""",[user])
    
    # get the change in value for the day
    try :
        day_gain = day_record[0]["total_value"] - day_record[0]["total_spent"]
        day_change_dec = ((Decimal(total_worth)-total_spent) - day_gain ) / day_gain
        day_change = bot_utilities.floored_percentage(day_change_dec,2) # format to percentage
        
        day_growth_str = "$"+str(round(Decimal(total_change) - day_gain,2))
    except :
        day_change = ""
        day_growth_str = "error"

    month_record = db.fetchAll("""select user_id, total_spent, total_value 
                                from performance_log 
                                where user_id = %s and date > now() - interval 30 day
                                order by date asc limit 1""",[user])
    
    # get the change in value for the month
    try: 
        month_gain = month_record[0]["total_value"] - month_record[0]["total_spent"]
        month_change_dec = ((Decimal(total_worth)-total_spent) - month_gain ) / month_gain
        month_change = bot_utilities.floored_percentage(month_change_dec,2) # format to percentage
        
        month_growth_str = "$"+str(round(Decimal(total_change) - month_gain,2))
    except :
        month_change = ""
        month_growth_str = "error"

    
    db.close()

    

    response = "*Spent:* $" + str(total_spent)+ "\n" \
        "*Value:* $" + str(total_worth) + "\n" \
        "*CHANGE:* $" + str(total_change) + " _(" + bot_utilities.floored_percentage((Decimal(total_change)/total_spent),2) + ")_ \n \n" \
        "_growth today: "+ day_growth_str + " (" + day_change + ")_\n" \
        "_30 day growth: " + month_growth_str + " (" + month_change+")_"
    

    bot_utilities.log_event(user + " requested performance: " + command)
    bot_utilities.post_to_channel(channel,response)


# user indicated they are adding a purchase
def add_purchase(user,channel,command) :
    db = database.Database()
    response = "something went wrong - add_purchase"
    # verify no current record is incomplete.  If so, blow it away
    db.runSql("""delete from purchases where record_complete = 0 and user_id = %s""",[user])

    # get supported coins
    supported_coins = db.fetchAll("select * from supported_coins order by sort_order desc")

    # did user give type?
    coin = None
    for supported_coin in supported_coins :
        if supported_coin["coin_name"].lower() in command :
            coin = supported_coin["coin_id"]
            break

    

    # begin purchase record
    if coin != None :
        db.runSql("""insert into purchases (user_id, date, coin_type, step, last_updated) values(%s, now(), %s, "amount",now())""",[user, coin])
        response = "Sounds great.  How much " + coin.upper() + " did you buy?"

    else :
        db.runSql("""insert into purchases (user_id, date, step, last_updated) values(%s, now(), "type",now())""", [user])
        response = "Sounds great.  What type of crypto did you buy?"

    # log event
    bot_utilities.log_event(user + " has begun a purchase record: " + command)

    # message user
    bot_utilities.post_to_channel(channel, response)


# user is creating a record. adding coin type
def add_type_to_purchase(user,channel,command,purchase_id):
    # check that a type was indicated in the command
    response = "something went wrong - add_type_to_purchase"

    db = database.Database()
    # get supported coins
    supported_coins = db.fetchAll("select * from supported_coins order by sort_order desc")
    db.close()

    # did user give type?
    coin = None
    for supported_coin in supported_coins :
        if supported_coin["coin_name"].lower() in command :
            coin = supported_coin["coin_id"]
            break

    if coin == None :
        response = "Sorry, you didn't give me a supported crypto type."
        bot_utilities.log_event("expected coin type and failed:" + user + ": " + command)

    else :
        db = database.Database()
        db.runSql("""update purchases set coin_type = %s, last_updated = now(), step = "amount" where purchase_id = %s""",[coin, purchase_id])
        db.close()
        response = "Sounds great.  How much " + coin.upper() + " did you buy?"
        
    bot_utilities.post_to_channel(channel,response)



# user is creating a record. adding amount
def add_amount_to_purchase(user,channel,command,purchase_id) :
    response = "something went wrong - add_amount_to_purchase"

    # try to get the number from the command
    parsed_amount = bot_utilities.parse_number_from_command(command)

    if parsed_amount == -9999 : # cound't get the number
        response = "sorry, I didn't catch that.  How much did you buy?"
        bot_utilities.log_event("trying to add amount to purchase and didn't parse number." + user + ": " + command)

    else : # update the record and move on
        db = database.Database()
        db.runSql("""update purchases set amount = %s, last_updated = now(), step = "usd_spent" where purchase_id = %s""",[parsed_amount, purchase_id])
        response = "Great.  Now how much of that filthy fiat money did you spend?"
        db.close()

    bot_utilities.post_to_channel(channel,response)


# user is on the last step of creating a purchase record
def add_usd_to_purchase(user,channel,command,purchase_id) :
    response = "something went wrong - add_usd_to_purchase"

    # try to get the number from the command
    parsed_amount = bot_utilities.parse_number_from_command(command)

    if parsed_amount == -9999 : # cound't get the number
        response = "sorry, I didn't catch that.  How much money did you spend?"
        bot_utilities.log_event("trying to add usd to purchase and didn't parse number." + user + ": " + command)

    else : # update the record and move on
        db = database.Database()
        db.runSql("""update purchases set usd_spent = %s, last_updated = now(), record_complete = 1, step = "complete" where purchase_id = %s""",[parsed_amount, purchase_id])
        response = "Great, you're all set."
        bot_utilities.log_event(user + " added a purchase")
        db.close()

    bot_utilities.post_to_channel(channel,response)


# user indicated they are adding a sale
def add_sale(user,channel,command) :
    db = database.Database()
    response = "something went wrong - add_sale"
    # verify no current record is incomplete.  If so, blow it away
    db.runSql("""delete from sales where record_complete = 0 and user_id = %s""",[user])

    # get supported coins
    supported_coins = db.fetchAll("select * from supported_coins order by sort_order desc")

    # did user give type?
    coin = None
    for supported_coin in supported_coins :
        if supported_coin["coin_name"].lower() in command :
            coin = supported_coin["coin_id"]
            break

    # begin sale record
    if coin != None :
        db.runSql("""insert into sales (user_id, date, coin_type, step, last_updated) values(%s, now(), %s, "amount",now())""",[user, coin])
        response = "Sounds great.  How much " + coin.upper() + " did you sell?"

    else :
        db.runSql("""insert into sales (user_id, date, step, last_updated) values(%s, now(), "type",now())""", [user])
        response = "Sounds great.  What type of crypto did you sell"

    # log event
    bot_utilities.log_event(user + " has begun a sale record: " + command)

    # message user
    bot_utilities.post_to_channel(channel, response)


# user is creating a record. adding coin type
def add_type_to_sale(user,channel,command,purchase_id):
    # check that a type was indicated in the command
    response = "something went wrong - add_type_to_sale"

    db = database.Database()
    # get supported coins
    supported_coins = db.fetchAll("select * from supported_coins order by sort_order desc")
    db.close()

    # did user give type?
    coin = None
    for supported_coin in supported_coins :
        if supported_coin["coin_name"].lower() in command :
            coin = supported_coin["coin_id"]
            break


    if coin == None :
        response = "Sorry, you didn't give me a valid crypto type."
        bot_utilities.log_event("expected coin type and failed:" + user + ": " + command)

    else :
        db = database.Database()
        db.runSql("""update sales set coin_type = %s, last_updated = now(), step = "amount" where purchase_id = %s""",[coin, purchase_id])
        db.close()
        response = "Sounds great.  How much " + coin.upper() + " did you sell?"
        
    bot_utilities.post_to_channel(channel,response)


# user is creating a record. adding amount
def add_amount_to_sale(user,channel,command,purchase_id) :
    response = "something went wrong - add_amount_to_sale"

    # try to get the number from the command
    parsed_amount = bot_utilities.parse_number_from_command(command)

    if parsed_amount == -9999 : # cound't get the number
        response = "sorry, I didn't catch that.  How much did you sell?"
        bot_utilities.log_event("trying to add amount to sale and didn't parse number." + user + ": " + command)

    else : # update the record and move on
        db = database.Database()
        db.runSql("""update sales set amount = %s, last_updated = now(), step = "usd_gained" where purchase_id = %s""",[parsed_amount, purchase_id])
        response = "Great.  How much USD did you get in return?"
        db.close()

    bot_utilities.post_to_channel(channel,response)


# user is on the last step of creating a purchase record
def add_usd_to_sale(user,channel,command,purchase_id) :
    response = "something went wrong - add_usd_to_sale"

    # try to get the number from the command
    parsed_amount = bot_utilities.parse_number_from_command(command)

    if parsed_amount == -9999 : # cound't get the number
        response = "sorry, I didn't catch that.  How much money did you get?"
        bot_utilities.log_event("trying to add usd to sale and didn't parse number." + user + ": " + command)

    else : # update the record and move on
        db = database.Database()
        db.runSql("""update sales set usd_gained = %s, last_updated = now(), record_complete = 1, step = "complete" where purchase_id = %s""",[parsed_amount, purchase_id])
        response = "Great, you're all set."
        bot_utilities.log_event(user + " added a sale")
        db.close()

    bot_utilities.post_to_channel(channel,response)

   
# lets the user request the current crypto prices
def show_prices(user,channel,command) :
    response = ""

    db = database.Database()
    coins = db.fetchAll("select * from supported_coins order by sort_order asc")

    for coin in coins :
        # fetch the previous pice
        records = db.fetchAll("""select * 
                                from price_history 
                                where coin = %s and date > now()-interval 24 hour order by date asc limit 1""",[coin['coin_id']])
        
        current_price = bot_utilities.get_current_price(coin['coin_id'].lower())

        try : # in case prices didn't get logged
            start_price = records[0]['price']
            change_pct = bot_utilities.floored_percentage((current_price-float(start_price)) / float(start_price),2)

        except:  
            start_price = 0
            change_pct = "error"
        

        # add to response
        response = response + "*" + coin['coin_id'] + " " + coin['coin_name']+ ":* $" + str(current_price) + " _(" + str(change_pct) + ")_ \n"

    
    bot_utilities.post_to_channel(channel, response)

    bot_utilities.log_event(user + " requested prices: " + command)




# user is in the middle of creating a record.  Handle it
def handle_ongoing_record_creation (user, channel, command, record_type):
    if record_type == "purchase" :
        db = database.Database()
        records = db.fetchAll("""select * from purchases where record_complete = 0 and user_id = %s order by last_updated desc limit 1""",[user])
        db.close()

        if records[0]["step"] == "type" :
            add_type_to_purchase(user,channel,command,records[0]["purchase_id"])

        elif records[0]["step"] == "amount" :
            add_amount_to_purchase(user,channel,command,records[0]["purchase_id"])

        elif records[0]["step"] == "usd_spent" :
            add_usd_to_purchase(user,channel,command,records[0]["purchase_id"])

    elif record_type == "sale" :
        db = database.Database()
        records = db.fetchAll("""select * from sales where record_complete = 0 and user_id = %s order by last_updated desc limit 1""",[user])
        db.close()

        if records[0]["step"] == "type" :
            add_type_to_sale(user,channel,command,records[0]["purchase_id"])

        elif records[0]["step"] == "amount" :
            add_amount_to_sale(user,channel,command,records[0]["purchase_id"])

        elif records[0]["step"] == "usd_gained" :
            add_usd_to_sale(user,channel,command,records[0]["purchase_id"])





