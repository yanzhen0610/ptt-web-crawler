# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

import os
import re
import sys
import requests
import argparse
import time
import threading
from bs4 import BeautifulSoup
from six import u

__version__ = '1.0'

# if python 2, disable verify flag in requests.get()
PTT_URL = 'https://www.ptt.cc'
VERIFY = True
if sys.version_info[0] < 3:
    VERIFY = False
    requests.packages.urllib3.disable_warnings()


def parse_articles(start, end, board, timeout=3):
    result = list()
    for i in range(end-start+1):
        index = start + i
        print('Processing index:', str(index))
        try:
            resp = requests.get(
                url = PTT_URL + '/bbs/' + board + '/index' + str(index) + '.html',
                cookies={'over18': '1'}, verify=VERIFY, timeout=timeout
            )
        except:
            continue
        if resp.status_code != 200:
            print('invalid url:', resp.url)
            continue
        soup = BeautifulSoup(resp.text, 'html.parser')
        divs = soup.find_all("div", "r-ent")
        threads = list()
        for div in divs:
            try:
                # ex. link would be <a href="/bbs/PublicServan/M.1127742013.A.240.html">Re: [問題] 職等</a>
                href = div.find('a')['href']
                link = PTT_URL + href
                article_id = re.sub('\\.html', '', href.split('/')[-1])
            except:
                continue
            thread = threading.Thread(target=lambda:
                result.append(parse(link, article_id, board, timeout)))
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()
    return result


def parse_article(article_id, board):
    link = PTT_URL + '/bbs/' + board + '/' + article_id + '.html'
    return parse(link, article_id, board)


def parse(link, article_id, board, timeout=3):
    print('Processing article:', article_id)
    try:
        resp = requests.get(url=link, cookies={'over18': '1'}, verify=VERIFY, timeout=timeout)
    except:
        return None
    if resp.status_code != 200:
        print('invalid url:', resp.url)
        return None
    soup = BeautifulSoup(resp.text, 'html.parser')
    main_content = soup.find(id="main-content")
    metas = main_content.select('div.article-metaline')
    author = ''
    title = ''
    date = ''
    if metas:
        author = metas[0].select('span.article-meta-value')[0].string if metas[0].select('span.article-meta-value')[0] else author
        title = metas[1].select('span.article-meta-value')[0].string if metas[1].select('span.article-meta-value')[0] else title
        date = metas[2].select('span.article-meta-value')[0].string if metas[2].select('span.article-meta-value')[0] else date

        # remove meta nodes
        for meta in metas:
            meta.extract()
        for meta in main_content.select('div.article-metaline-right'):
            meta.extract()

    # remove and keep push nodes
    pushes = main_content.find_all('div', class_='push')
    for push in pushes:
        push.extract()

    try:
        ip = main_content.find(text=re.compile(u'※ 發信站:'))
        ip = re.search('[0-9]*\.[0-9]*\.[0-9]*\.[0-9]*', ip).group()
    except:
        ip = "None"

    # 移除 '※ 發信站:' (starts with u'\u203b'), '◆ From:' (starts with u'\u25c6'), 空行及多餘空白
    # 保留英數字, 中文及中文標點, 網址, 部分特殊符號
    filtered = [ v for v in main_content.stripped_strings if v[0] not in [u'※', u'◆'] and v[:2] not in [u'--'] ]
    expr = re.compile(u(r'[^\u4e00-\u9fa5\u3002\uff1b\uff0c\uff1a\u201c\u201d\uff08\uff09\u3001\uff1f\u300a\u300b\s\w:/-_.?~%()]'))
    for i in range(len(filtered)):
        filtered[i] = re.sub(expr, '', filtered[i])

    filtered = [_f for _f in filtered if _f]  # remove empty strings
    filtered = [x for x in filtered if article_id not in x]  # remove last line containing the url of the article
    content = ' '.join(filtered)
    content = re.sub(r'(\s)+', ' ', content)
    # print 'content', content

    # push messages
    p, b, n = 0, 0, 0
    messages = []
    for push in pushes:
        if not push.find('span', 'push-tag'):
            continue
        push_tag = push.find('span', 'push-tag').string.strip(' \t\n\r')
        push_userid = push.find('span', 'push-userid').string.strip(' \t\n\r')
        # if find is None: find().strings -> list -> ' '.join; else the current way
        push_content = push.find('span', 'push-content').strings
        push_content = ' '.join(push_content)[1:].strip(' \t\n\r')  # remove ':'
        push_ipdatetime = push.find('span', 'push-ipdatetime').string.strip(' \t\n\r')
        messages.append( {'push_tag': push_tag, 'push_userid': push_userid, 'push_content': push_content, 'push_ipdatetime': push_ipdatetime} )
        if push_tag == u'推':
            p += 1
        elif push_tag == u'噓':
            b += 1
        else:
            n += 1

    # count: 推噓文相抵後的數量; all: 推文總數
    message_count = {'all': p+b+n, 'count': p-b, 'push': p, 'boo': b, "neutral": n}

    # print 'msgs', messages
    # print 'mscounts', message_count

    # json data
    data = {
        'url': link,
        'board': board,
        'article_id': article_id,
        'article_title': title,
        'author': author,
        'date': date,
        'content': content,
        'ip': ip,
        'message_count': message_count,
        'messages': messages
    }
    # print 'original:', d
    return data


def getLastPage(board, timeout=3):
    try:
        content = requests.get(
            url= 'https://www.ptt.cc/bbs/' + board + '/index.html',
            cookies={'over18': '1'}, timeout=timeout
        ).content.decode('utf-8')
    except:
        return -1
    first_page = re.search(r'href="/bbs/' + board + '/index(\d+).html">&lsaquo;', content)
    if first_page is None:
        return 1
    return int(first_page.group(1)) + 1
