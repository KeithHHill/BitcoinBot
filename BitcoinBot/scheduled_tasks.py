import bot_utilities
import sys


if __name__ == "__main__":
    arguments = sys.argv[1:]
    #bot_utilities.log_performance()
    if len(arguments) > 0 :
        if arguments[0] == "log_performance" :
            bot_utilities.log_performance()
            sys.exit()