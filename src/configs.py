import json 
import re
import sys
import os
import threading
import time
import click
import pytz
from pathlib import Path
import sqlite3
import datetime as dt
import requests
from telegram import Bot, InputMediaPhoto, InputMediaVideo, InputMediaAnimation, MessageEntity, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, MessageEntity
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler

from persiantools.jdatetime import JalaliDate

import tweepy

working_dir = os.path.dirname(os.path.abspath(__file__))
creds_file = os.path.join(working_dir, 'creds.json')
db_conf_file = os.path.join(working_dir, 'db_conf.json')


import utils