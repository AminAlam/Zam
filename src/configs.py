"""
Configuration module for Zam Telegram Bot.
Loads environment variables and provides shared imports.
"""

import os
import json
import re
import sys
import threading
import time
import random
import datetime as dt

import click
import requests
from pathlib import Path
from dotenv import load_dotenv

from telegram import Bot, InputMediaPhoto, InputMediaVideo, InputMediaAnimation, MessageEntity, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler

from persiantools.jdatetime import JalaliDate
from tweetcapture import TweetCapture

# Load environment variables from .env file
load_dotenv()

# Working directory
working_dir = os.path.dirname(os.path.abspath(__file__))
