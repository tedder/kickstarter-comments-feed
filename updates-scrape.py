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
 "BuildOne 3D printer": "https://www.kickstarter.com/projects/robotic-industries/buildone-99-3d-printer-w-wifi-and-auto-bed-levelin"
}

def parse_update_page(update_page_url):
  r = requests.get(update_page_url)
  update_page_text = r.text
  tree = lxml.html.fromstring(update_page_text)

  page_ret = []
  with open('/tmp/ks.txt', 'w') as f:
    f.write(update_page_text)
  #update_text = tree.xpath("//div[contains(@class, 'project_post_summary')]")
  #update_text = tree.xpath("//div[contains(concat(' ', normalize-space(@class), ' '), ' body ')]/*")
  update_text = tree.xpath("//div[contains(@class, 'body')]")
  #update_text = tree.xpath("//div[tokenize(@class,'\s+')='body']")
  #print("UT length", len(update_text))

  if len(update_text) == 0:
    raise Exception("unexpected number of update text returns: " + str(update_text))
  else:
    # > 1 is okay, it's just multiple paragraphs
    text_accum = []
    for c_para in update_text:
      text_accum.append(etree.tostring(c_para))
      #print(etree.tostring(c_para))
  return b"\n".join((text_accum)).decode('utf-8')


def parse_update(update_container, pageurl):
  # this show match the JSON feed spec for a single item.
  url = update_container.get('href')
  #print("url: {}".format(url))
  ret = {
    'id': re.sub(r'(.*\/)(\d+)', "\\2", url),
    'url': 'https://kickstarter.com' + url
  }
  #print("ret_url: {}".format(ret["url"]))
  times = update_container.xpath("p[contains(@class, 'grid-post__date')]/time")
  #print("times: {}".format(times))
  if len(times) != 1:
    raise Exception("unexpected number of dates: " + str(update_text))
  else:
    ret['date_published'] = times[0].get('datetime')
  #print("DP: {}".format(ret['date_published']))

  ret['content_html'] = parse_update_page(ret['url'])
  #print(json.dumps(ret))
  #print(ret)

  return ret

def write_json_feed(_items, pageurl, url_snippet, project_title):
  s3_key = 'rss/ks/updates/' + url_snippet + '.json'
  feed_url = 'https://dyn.tedder.me/' + s3_key
  feedj = {
    'version': 'https://jsonfeed.org/version/1',
    'user_comment': "parsed from Kickstarter because I was tired of refreshing update pages. Will document if desired.",
    'title': '{} updates / scraped from Kickstarter'.format(project_title),
    'home_page_url': pageurl,
    'feed_url': feed_url,
    'author': { 'name': 'tedder', 'url': 'https://tedder.me' },
    # expired <- true when this feed is dead
    'items': _items
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


def parse_project(project_url, project_title):
  project_updates_url = project_url + '/updates'
  #print(project_updates_url)
  r = requests.get(project_updates_url)
  project_updates_text = r.text
  #print(len(project_updates_text))
  tree = lxml.html.fromstring(project_updates_text)
  #print(tree)
  #print(comments_text)

  _items = []
  updates_container = tree.xpath("//a[contains(@class, 'grid-post')]")
  #updates_container = tree.xpath("//a[contains(@class, 'grid-post')]//*")
  #updates_container = tree.findall("/a[contains(@class, 'grid-post')]")
  #print(comments_container)
  #print(updates_container, type(updates_container))

  for update_container in updates_container:
    #print("pc")
    _items.append(parse_update(update_container, project_updates_url))
    if len(_items) >= 10: break

  scrubbed_url = re.sub(r"[^a-zA-Z\-_0-9]", "-", project_title.lower())
  write_json_feed(_items, project_url, scrubbed_url, project_title)

for title,u in PROJECT_URLS.items():
  #c_u = "https://www.kickstarter.com/projects/" + u + "/comments"
  parse_project(u, title)

