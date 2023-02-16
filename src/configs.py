import json 
import re
import sys
import os
import threading
import time

from pathlib import Path
import sqlite3
import datetime as dt

from telegram import Bot, InputMediaPhoto, InputMediaVideo, MessageEntity, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, MessageEntity
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler

from persiantools.jdatetime import JalaliDate

import tweepy

working_dir = os.path.dirname(os.path.abspath(__file__))
creds_file = f"{working_dir}/creds.json"
db_conf_file = f"{working_dir}/db_conf.json"

time_diff = {'hours':1, 'minutes':30}

import utils