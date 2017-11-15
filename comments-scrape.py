#!/usr/bin/env python3

import boto3
import json
import requests
from lxml import etree
import lxml
import lxml.html
import re

# using the JSON feed spec: https://jsonfeed.org/version/1

PROJECT_URL = "robotic-industries/buildone-99-3d-printer-w-wifi-and-auto-bed-levelin"
COMMENTS_PAGE_URL = "https://www.kickstarter.com/projects/" + PROJECT_URL + "/comments"
SCRUBBED_PROJECT_URL = re.sub(r"[^a-zA-Z\-_0-9]", "-", PROJECT_URL)

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
  else:
    raise Exception("unexpected number of comment date returns: " + str(comment_date))

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

def write_json_feed(comments, pageurl, comment_url_snippet):
  s3_key = 'rss/ks/comments/' + comment_url_snippet + '.json'
  feed_url = 'https://dyn.tedder.me/' + s3_key
  feedj = {
    'version': 'https://jsonfeed.org/version/1',
    'user_comment': "parsed from Kickstarter because I was tired of refreshing comments pages. Documentation/intro should be on Medium, also <https://github.com/tedder/kickstarter-comments-feed/>. It isn't generified- this is just the first pass.",
    'title': 'BuildOne comments / scraped from Kickstarter',
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


r = requests.get(COMMENTS_PAGE_URL)
#print(COMMENTS_PAGE_URL)
comments_text = r.text
tree = lxml.html.fromstring(comments_text)
#print(comments_text)

comments_ret = []
comments_container = tree.xpath("//ol[contains(@class, 'comments')]/li[contains(@class, 'comment')]")
#print(comments_container)

for comment_container in comments_container:
  #print("pc")
  comments_ret.append(parse_comment(comment_container, COMMENTS_PAGE_URL))

write_json_feed(comments_ret, COMMENTS_PAGE_URL, SCRUBBED_PROJECT_URL)

