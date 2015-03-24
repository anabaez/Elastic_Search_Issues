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
# Script version. It's recommended to increment this with every change, to make
# debugging easier.
VERSION = '0.9.0'


# Set up logging.
log = logging.getLogger('{0}[{1}]'.format(os.path.basename(sys.argv[0]),
                                          os.getpid()))
#how do I validate this properly?
def validate_per_page(per_page):
    try:
        if int(per_page) <= 100 and int(per_page) > 0:
            return per_page
    except:
        print '--per_page argument must be within range 1-100'
        Ex

def get_comments_by_url(url, auth):

    #create cachekey
    m = hashlib.md5()
    m.update(url)
    key = m.hexdigest()

    cache_file_path = "%s/%s.json" % (CACHE_FOLDER, key)

    try:
        #HIT
        with open(cache_file_path, 'rb') as cache_file:
            return json.loads(cache_file.read())
    except IOError:
        #MISS
        result = requests.get(url, auth=auth)
        data = result.json()

        with open(cache_file_path, 'wb') as cache_file:
            cache_file.write(json.dumps(data, indent=4))
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


def main(args, config):
    #uploader
    uploader = ItemUploader(project_id=args.project_id,
                            source_name=args.source_name,
                            token=args.token,
                            cluster=args.cluster)
    url = args.url
    user = (args.user, args.password)
    payload = {'per_page':args.per_page,'page':1, 'state':'all', 'sort':'updated'}

    r = requests.get(url, auth=user, params=payload)
    request_count = 0
    issue_count = 0
    while True:
        items = []
        #keep track of iterations
        issue_count += (int(per_page))
        request_count += 1

        for issue in issues: 
            item={}
            item['title'] = issue['title']
            item['id'] = issue['id']
            item['link'] = issue['html_url']
            item['created_at'] = issue['updated_at'].strip('Z')

            #issue closed at
            if issue['closed_at'] != None:
                closed_at = ' - ' + issue['closed_at'].strip('Z')
            else:
                closed_at = ''

            body = u"""
                <html>
                    <head> 
                        <H6> 
                Status: {status}  {closed_at} <br/>
                Author: {author} <br/>
                Updated: {updated}
                        </H6>
                    </head>
                    <pre>
                    <body>
                    {body}
                    </body>
                    </pre>
                </html>
                """.format(
                        author = issue['user']['login'],
                        updated = issue['updated_at'],
                        body = issue['body'],
                        status = issue['state'],
                        closed_at = closed_at)

            #if the ticket has comments
            if issue['comments'] != '0':
                comments = get_comments_by_url(issue['comments_url'], auth=user)
                for comment in comments:

                    request_count += 1
                    body += u"\n" + u"""
                        <html>
                            <head>
                                <H6>
                                    Comment: <br/>
                                    Author: {author} <br/>
                                    Updated: {updated}
                                </H6>
                            </head>
                            
                                <body>
                                {body}
                                </body>
                            
                        </html>
                        """.format(
                                author=comment['user']['login'],
                                updated=comment['updated_at'].strip('Z'),
                                body=comment['body'])        
            item['body'] = body

            #Add keywords
            ks = {}
            if issue['locked'] == True:
                ks['locked'] = 'locked'
            ks['assignee'] = issue['assignee']['login']
            ks['milestone'] = issue['milestone']
            ks['comments'] = str(issue['comments'])
            ks['status'] = issue['state']
            ks['id'] = issue['id']
            ks['labels'] = []
            for label in issue['labels']:
                ks['labels'].append(label['name'])
            item['keywords'] = ks

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
                        help='number of items to appear per request')
    parser.add_argument('--max_requests',help='maximum number of requests')
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
