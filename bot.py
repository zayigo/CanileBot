import json
import random
import re
import urllib
from datetime import date

import pause
import requests
import telebot
from bs4 import BeautifulSoup
from tinydb import Query, TinyDB

import config as cfg

Dogs = Query()
database = TinyDB("database.json")


class Bot():
    def __init__(self, api_key, channel_id, templates):
        self.api_key = api_key
        self.channel_id = channel_id
        self.new_dogs = []
        self.msg_template = templates
        self.bot = telebot.TeleBot(self.api_key, parse_mode="html")

    def load_new(self):
        self.new_dogs = database.search(Dogs.new is True)
        self.download_images()
        print(f"Found {len(self.new_dogs)} new dogs")

    def download_images(self):
        for dog in self.new_dogs:
            for image in dog["images"]:
                print(f"Downloading {image}")
                response = requests.get(image, stream=True, timeout=30)
                path = f"./images/{image.split('/')[-1]}"
                with open(path, 'wb') as f:
                    for chunk in response:
                        f.write(chunk)

    def send_messages(self):
        print(f"Sending {len(self.new_dogs)} messages")
        emojis = ["🐶", "🦮", "🐕", "🐕‍🦺", "🐩"]
        for dog in self.new_dogs:
            pause.seconds(10)
            if len(dog["desc"]) > 900:
                dog["desc"] = dog["desc"][:900] + "..."
            text = self.msg_template.format(
                emoji=random.choice(emojis), name=dog["name"], description=dog["desc"], url=dog["url"]
            )
            try:
                if len(dog["images"]) > 1:
                    input_media = []
                    for url in dog["images"]:
                        path = f"./images/{url.split('/')[-1]}"
                        with open(path, "rb") as image:
                            f = image.read()
                            input_media.append(telebot.types.InputMediaPhoto(f))
                    sent_images = self.bot.send_media_group(self.channel_id, media=input_media)
                    self.bot.edit_message_caption(
                        text,
                        chat_id=self.channel_id,
                        message_id=sent_images[0].message_id,
                    )
                else:
                    self.bot.send_photo(
                        self.channel_id,
                        caption=text,
                        photo=dog["images"][0],
                    )
            except Exception:
                print(f"Message error {dog}")
            else:
                print(f"Message sent {dog}")
                database.update({'new': False}, Dogs.url == dog["url"])


class Scraper():
    def __init__(self, url) -> None:
        self.url = url
        self.dog_urls = []

    def get_details(self, url):
        content = requests.get(url).text
        soup = BeautifulSoup(content, 'lxml')
        title = soup.find("title").text.split("|")[0].lower()
        title = title.replace("in cessione", "").strip()
        article = soup.find("article")
        description = article.getText(strip=True, separator=" ")
        description = description.replace("\u2019", "").replace("\u00e8", "")
        images = [img["src"] for img in article.find_all("img")]
        return {
            "name": title.title(), "desc": re.sub(r"\s{2,}", " ", description).strip(), "images": list(set(images))
        }

    def check_duplicates(self):
        for url in self.dog_urls:
            dog = {"url": url}
            if database.search(Dogs.fragment(dog)):
                print(f"Alread saved {dog}")
                continue
            dog["date"] = date.today().isoformat()
            dog["new"] = True
            dog = {**dog, **self.get_details(url)}
            print(f"🐶 Found new dog! {dog}")
            database.insert(dog)

    def get_dogs(self):
        content = requests.get(self.url).text
        soup = BeautifulSoup(content, 'lxml')
        divs = soup.find("div", class_="grid").find_all("div", class_="rounded-default", recursive=False)
        self.dog_urls = [urllib.parse.urljoin(self.url, d.find("a", href=True)["href"]) for d in divs]
        self.check_duplicates()


if __name__ == "__main__":
    sc = Scraper(cfg.URL_ADOPTIONS)
    sc.get_dogs()
    bot = Bot(cfg.URL_ADOPTIONS, cfg.TELEGRAM_API_KEY, cfg.MSG_TEMPLATE)
    bot.load_new()
    bot.send_messages()
    print(json.dumps({"complete": 1}))
