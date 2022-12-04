import json 
import re
import sys
import os
import threading
import time

from pathlib import Path
import sqlite3
import datetime as dt
import utils

from telegram import Bot, InputMediaPhoto, InputMediaVideo, MessageEntity, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, MessageEntity
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler

creds_file = "/home/amin/Documents/Twitter_Parser/src/creds.json"
db_conf_file = "/home/amin/Documents/Twitter_Parser/src/db_conf.json"
