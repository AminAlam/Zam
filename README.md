<div align="center">
  <br/>
<h1>Zam</h1>
  
<br/>
<img src="https://img.shields.io/badge/Python-14354C?style=for-the-badge&logo=python&logoColor=white" alt="built with Python3" />
<img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Telegram_logo.svg/800px-Telegram_logo.svg.png" style="width:3%" />
<img src="https://www.svgrepo.com/show/271093/twitter.svg" style="width:3%" />
</div>

----------

Zam: A Telegram/Twitter Bot for posting tweets to Telegram channels

<table border="0">
 <tr>
    <td><p align="justify">This program is dedicated to <a href="https://en.wikipedia.org/wiki/Ruhollah_Zam">Roohollah Zam</a>. 
      He was an Iranian activist and journalist. Zam played a high-profile role in the 2017–2018 Iranian protests, to which he devoted special coverage at the time. In June 2020, an Iran court found him guilty of "corruption on earth" for running a popular anti-government forum, which officials said had incited the 2017–2018 Iranian protests. He was sentenced to death by the regime court and was executed on 12 December 2020.
      </p>
</td>
    <td><img src="https://cdn.vox-cdn.com/thumbor/MZpfWZ4-9fV_LDEJihk5TAt_ILw=/0x0:3270x2142/1820x1213/filters:focal(1646x1148:2168x1670):format(webp)/cdn.vox-cdn.com/uploads/chorus_image/image/68502792/GettyImages_1223515476.0.jpg" alt="Roohollah Zam" width=800 /></td>
 </tr>
</table>


----------
## Table of contents			
   * [Introduction](https://github.com/AminAlam/Zam#overview)
   * [Installation](https://github.com/AminAlam/Zam#installation)
   * [Usage](https://github.com/AminAlam/Zam#usage)
   * [How It Works](https://github.com/AminAlam/Zam#how-it-works)

----------
## Overview
<p align="justify">
 Zam is a Telegram/Twitter bot which can accept tweet urls and post the tweets to a Telegram channel. Zam downloads all the media of the tweets using telegram servers so there is no downloading/uploading on your server side.
</p>

----------
## Installation

### Source code
- Clone the repository or download the source code.
- cd into the repository directory.
- Run `pip3 install -r requirements.txt` or `pip install -r requirements.txt`

## Usage
To run the program, use the following command:
```console
Amin@Maximus:Zam $ python3 src/main.py
```

To learn more about the options, you can use the following command:
```console
Amin@Maximus:Zam $ python3 src/main.py --help

Usage: main.py [OPTIONS]

  Zam: A Telegram Bot for posting tweets in a Telegram channel

Options:
  --time_diff TEXT                Difference between the time of the tweet and
                                  the time of the server running the bot.
                                  Format: HOURS:MINUTES  [default: 0:30]
  --mahsa_message BOOLEAN         A message about Mahsa Amini's murder will be
                                  sent to the channel with a timer which is
                                  updated evety few seconds.  [default: True]
  --gpt_suggestions_rate INTEGER  A GPT language model will randomly complete
                                  some short tweets with this rate. 0 means no
                                  suggestoins  [default: 0]
  --reference_snapshot BOOLEAN    A snapshot of the reference tweets (Qouted
                                  tweet or the tweet which main tweet is a
                                  reply to) will be set as one of the media of
                                  the post. Note that this feature needs
                                  chromium to function  [default: True]
  --num_tweets_to_preserve INTEGER RANGE
                                  Number of tweets to be saved in the
                                  database. Only last num_tweets_to_preserve
                                  tweets in the line will be preserved and the
                                  old ones will be deleted  [default: 1000;
                                  500<=x<=5000]
```
