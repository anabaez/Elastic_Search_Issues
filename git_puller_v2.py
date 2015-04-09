#!/usr/bin/env python
"""
This is a file to pull content from the Github elastic search issues API
"""
import argparse
import ConfigParser
import logging
import os
import sys
import time
from squirro_client import ItemUploader
import requests
import getpass
import hashlib
import json
import markdown

# Script version. It's recommended to increment this with every change, to make
# debugging easier.
VERSION = '0.9.0'


# Set up logging.
log = logging.getLogger('{0}[{1}]'.format(os.path.basename(sys.argv[0]),
                                          os.getpid()))
def pretty_print(obj):
    print json.dumps(obj, indent=4, sort_keys=True)
    return

#how do I validate this properly?
# def validate_per_page(per_page):
#     try:
#         if int(per_page) <= 100 and int(per_page) > 0:
#             return per_page
#     except Exception:
#         print '--per_page argument must be within range 1-100'

def get_comments_by_url(cache_folder, url, auth):

    #create cachekey
    m = hashlib.md5()
    m.update(url)
    key = m.hexdigest()

    cache_file_path = "%s/%s.json" % (cache_folder, key)

    try:
        #HIT
        with open(cache_file_path, 'rb') as cache_file:
            print 'comment already uploaded'
            return json.loads(cache_file.read())
    except IOError:
        #MISS
        result = requests.get(url, auth=auth)
        data = result.json()

        with open(cache_file_path, 'wb') as cache_file:
            cache_file.write(json.dumps(data, indent=4))
            print 'new request'
        return data

def parse_link_header(headers):

    if not headers.get('link'):
        return None

    #get all the links
    links = headers.get('link').split(',')

    next_link = None

    #look for the next link

    for link in links:
        if link.find('\"next\"') == -1:
            continue
        #extract the next url
        return link.split(';')[0].strip().strip('<').strip('>')
    return None

def create_squirro_item(issue):
    """create squirro item from issue, excluding keywords and comments"""

    item = {}
    item['title'] = issue['title']
    item['id'] = issue['id']
    item['link'] = issue['html_url']
    issue['updated_at'] = issue['updated_at'].strip('Z')
    item['created_at'] = issue['updated_at']

    if issue['closed_at'] != None:
        closed_at = ' - ' + issue['closed_at'].strip('Z')
    else:
        closed_at = ''

    item['body'] = u"""
        <h5>
            Status: {status}  {closed_at} <br/>
            Author: {author} <br/>
            Updated: {updated}
        </h5>
            {body}
            """.format(author=issue['user']['login'],
                       updated=issue['updated_at'],
                       body=markdown.markdown(issue['body']),
                       status=issue['state'],
                       closed_at=closed_at)
    return item

def add_comments(body, comments):
    for comment in comments:
        #request_count += 1
        body += u"\n" + u"""
                        <h5>
                        <hr>
                        Comment <br/>
                        Author: {author} <br/>
                        Updated: {updated}
                        </h5>

                        {body}
            """.format(author=comment['user']['login'],
                       updated=comment['updated_at'].strip('Z'),
                       body=markdown.markdown(comment['body']))
    return body

def add_keywords(issue):
    """returns a dictionary of keywords"""
    ks = {}
    if issue['locked'] == True:
        ks['locked'] = 'locked'
    if  issue['milestone']:
        ks['milestone'] = issue['milestone']
    ks['comments'] = str(issue['comments'])
    ks['status'] = issue['state']
    ks['id'] = issue['id']
    ks['labels'] = []
    for label in issue['labels']:
        ks['labels'].append(label['name'].replace(':', ''))
    return ks

def main(args, config):
    #uploader

    cache_folder = config.get('squirro', 'cache_folder')
    url = config.get('git_credentials', 'url')
    username = config.get('git_credentials', 'user')
    password_prompt = 'Github password for user %s: ' % username
    password = getpass.getpass(prompt=password_prompt)
    user = (username, password)
    uploader = ItemUploader(project_id=config.get('squirro', 'project_id'),
                            source_name=config.get('squirro', 'source_name'),
                            token=config.get('squirro', 'token'),
                            cluster=config.get('squirro', 'cluster'))



    payload = {'per_page':str(args.per_page), 'page':1, 'state':'all', 'sort':'updated'}
    print config.get('git_credentials', 'user')

    r = requests.get(url, auth=user, params=payload)
    request_count = 0
    issue_count = 0
    while True:
        items = []
        issues = r.json()
        if request_count >= args.max_requests:
            print '%s requests made, ending script' % str(request_count)
            break

        #keep track of iterations
        issue_count += (int(args.per_page))
        request_count += 1

        for issue in issues:
            item = create_squirro_item(issue)

            if issue['comments'] != '0':
                comments = get_comments_by_url(cache_folder, issue['comments_url'], auth=user)
                item['body'] = add_comments(item['body'], comments)

            item['keywords'] = add_keywords(issue)
            items.append(item)

            #when the loop reaches the last page of issues there is no more 'rel:next' in r.headers
            next = parse_link_header(r.headers)
            if not next:
                break
            r = requests.get(next, auth=user)

        uploader.upload(items)
        print 'Uploaded %s issues' % str(issue_count)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', action='version', version=VERSION)
    parser.add_argument('--verbose', '-v', action='count',
                        help='Show additional information.')
    parser.add_argument('--log-file', dest='log_file',
                        help='Log file on disk.')
    parser.add_argument('--config-file', dest='config_file',
                        help='Configuration file to read settings from.')
    parser.add_argument('--per_page', '-pp', default='100',
                        help='number of items to appear per request, default = 100')
    parser.add_argument('--max_requests', help='maximum number of requests, default = 100', default=100)
    return parser.parse_args()


def setup_logging(args):
    """Set up logging based on the command line options.
    """
    # Set up logging
    fmt = '%(asctime)s %(name)s %(levelname)-8s %(message)s'
    if args.verbose == 1:
        level = logging.INFO
        logging.getLogger(
            'requests.packages.urllib3.connectionpool').setLevel(logging.WARN)
    elif args.verbose >= 2:
        level = logging.DEBUG
    else:
        # default value
        level = logging.WARN
        logging.getLogger(
            'requests.packages.urllib3.connectionpool').setLevel(logging.WARN)

    # configure the logging system
    if args.log_file:
        out_dir = os.path.dirname(args.log_file)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir)
        logging.basicConfig(
            filename=args.log_file, filemode='a', level=level, format=fmt)
    else:
        logging.basicConfig(level=level, format=fmt)

    # Log time in UTC
    logging.Formatter.converter = time.gmtime


def get_config(args):
    """Parse the config file and return a ConfigParser object.

    Always reads the `main.ini` file in the current directory (`main` is
    replaced by the current basename of the script).
    """
    cfg = ConfigParser.SafeConfigParser()

    root, _ = os.path.splitext(__file__)
    files = [root + '.ini']
    if args.config_file:
        files.append(args.config_file)

    log.debug('Reading config files: %r', files)
    cfg.read(files)
    return cfg


# This is run if this script is executed, rather than imported.
if __name__ == '__main__':
    args = parse_args()
    setup_logging(args)
    config = get_config(args)

    log.info('Starting process (version %s).', VERSION)
    log.debug('Arguments: %r', args)

    # run the application
    try:
        main(args, config)
    except Exception as e:
        log.exception('Processing error')
