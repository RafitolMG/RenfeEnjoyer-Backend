#!/bin/bash
apt-get update
apt-get install -y wget unzip xvfb libxi6 libgconf-2-4
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
dpkg -i google-chrome-stable_current_amd64.deb || apt-get -f install -y

# Instalar ChromeDriver (versión estable)
LATEST=$(curl -sS https://chromedriver.storage.googleapis.com/LATEST_RELEASE)
wget -O chromedriver.zip "https://chromedriver.storage.googleapis.com/$LATEST/chromedriver_linux64.zip"
unzip chromedriver.zip
mv chromedriver /usr/local/bin/
chmod +x /usr/local/bin/chromedriver