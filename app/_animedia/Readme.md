# Animedia player

## DISCLAIMER 
This application is for personal use only and should not be used to infringe copyright or other laws.

### This app uses 
    BeautifulSoup
    Playwright

### to find links of video stream and then open in VLC player automatically.

## Setup

Clone repository:
```bash
git clone https://github.com/mr9733n/get-anime.git
```

Installing Dependencies:

Before running the application, make sure you have Python 3 and VLC Player installed. You will also need to install the necessary dependencies:
Install the necessary libraries using pip:

```bash
cd get-anime
pip install -r requirements.txt
```

## Use
```commandline
py app/_animedia/demo.py
```

## Build
```commandline
pyinstaller animediaPlayerDemo.spec --noconfirm
```