#!/usr/bin/env python3

import boto3
import json
import requests
from lxml import etree
import lxml
import lxml.html
import re

# using the JSON feed spec: https://jsonfeed.org/version/1
# s3 location: dyn.tedder.me/rss/ks/comments/

PROJECT_URLS = {
  "BuildOne": "robotic-industries/buildone-99-3d-printer-w-wifi-and-auto-bed-levelin",
  "Memistore": "memistore/memistore-store-your-extra-memory-cards-and-images",
  "Pi Zero Docking Hub": "makerspot/raspberry-pi-zero-docking-hub",
  "RePLAy 3D Filament and Recycling Program Pre-Sale!": "1239295865/replay-3d-filament-and-recycling-program-pre-sale",
  "Maker UNO": "1685732347/6-maker-uno-simplifying-arduino-for-education",
  "Easy Peelzy": "1011650524/easy-peelzy",
  "ZiFlex": "1856422226/ziflex-flexible-and-magnetic-build-platform-for-3d",
  "amplify aptx headphone amplifier": "auris/amplify-the-ultimate-wireless-headphone-amplifier",
  "3dp professor low-poly dinosaurs": "3dpprofessor/low-poly-dinos-dinosaur-3d-models-by-3d-printing-p",
  "Huell Howser's greatest hits": "kcet/bring-back-huells-greatest-hits",
}

def parse_comment(comment_container, pageurl):
  # this show match the JSON feed spec for a single item.
  ret = {
    'id': pageurl + '#' + comment_container.get('id'),
    'url': pageurl + '#' + comment_container.get('id')
  }
  comment_author = comment_container.xpath("div[contains(@class, 'comment-inner')]/div/h3/a[contains(@class, 'author')]")

  if len(comment_author) == 1:
    ret['author'] = {
      'name': comment_author[0].text,
      'url': 'https://kickstarter.com/' + comment_author[0].get("href")
    }
  else:
    raise Exception("unexpected number of comment author returns: " + str(comment_author))

  comment_date = comment_container.xpath("div[contains(@class, 'comment-inner')]/div/h3/span/a/data")
  if len(comment_date) == 1:
    # surrounded by quotes, which lxml doesn't remove
    ret['date_published'] = comment_date[0].get('data-value').replace('"', '')
  elif len(comment_date) == 0: # this happens sometimes
    pass
  else:
    raise Exception("unexpected number of comment date returns: {}, cid: {}, url: {}".format(str(comment_date), comment_container.get('id'), pageurl))


  comment_text = comment_container.xpath("div[contains(@class, 'comment-inner')]/div/p")
  if len(comment_text) == 0:
    raise Exception("unexpected number of comment text returns: " + str(comment_text))
  else:
    # > 1 is okay, it's just multiple paragraphs
    text_accum = []
    for c_para in comment_text:
      text_accum.append(etree.tostring(c_para))
  ret['content_html'] = b"\n".join((text_accum)).decode('utf-8')
  #print(json.dumps(ret))

  return ret

def write_json_feed(comments, pageurl, comment_url_snippet, project_title):
  s3_key = 'rss/ks/comments/' + comment_url_snippet + '.json'
  feed_url = 'https://dyn.tedder.me/' + s3_key
  feedj = {
    'version': 'https://jsonfeed.org/version/1',
    'user_comment': "parsed from Kickstarter because I was tired of refreshing comments pages. Documentation/intro on Medium, also <https://github.com/tedder/kickstarter-comments-feed/>.",
    'title': '{} comments / scraped from Kickstarter'.format(project_title),
    'home_page_url': pageurl,
    'feed_url': feed_url,
    'author': { 'name': 'tedder', 'url': 'https://tedder.me' },
    # expired <- true when this feed is dead
    'items': comments
  }

  s3 = boto3.client('s3')
  s3.put_object(
    ACL='public-read',
    Body=json.dumps(feedj),
    Bucket='dyn.tedder.me',
    Key=s3_key,
    ContentType='application/json',
    CacheControl='public, max-age=30' # todo: 3600
  )
  #print("updated: {}".format(feed_url))


def parse_project(comment_page_url, project_url, project_title):
  r = requests.get(comment_page_url)
  comments_text = r.text
  tree = lxml.html.fromstring(comments_text)
  #print(comments_text)

  comments_ret = []
  comments_container = tree.xpath("//ol[contains(@class, 'comments')]/li[contains(@class, 'comment')]")
  #print(comments_container)

  for comment_container in comments_container:
    #print("pc")
    comments_ret.append(parse_comment(comment_container, comment_page_url))

  scrubbed_url = re.sub(r"[^a-zA-Z\-_0-9]", "-", project_url)
  write_json_feed(comments_ret, comment_page_url, scrubbed_url, project_title)

for title,u in PROJECT_URLS.items():
  c_u = "https://www.kickstarter.com/projects/" + u + "/comments"
  parse_project(c_u, u, title)
