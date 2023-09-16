#!/usr/bin/env python3
##########################################################################################
# This script sends a slack notification based on a custom webhook, and can be run as a CLI
# or included and used from another python script.  Easy  :)
# Written by Farley <farley@neonsurge.com>
##########################################################################################

# Libraries, json for parsing JSON, and cli option parser
import json
from pprint import pprint
from optparse import OptionParser
# Imports for reading from stdin
import sys
import os
import select
# Import for calling the slack URL
import urllib.request

# Our helper to get STDIN if it exists in a non-blocking fashion
def getBodyFromSTDIN():
    output = ""
    while sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
      line = sys.stdin.readline()
      if line:
        output = output + line + "\n"
      else: # an empty line means stdin has been closed
        return output.strip()
    else:
      return False;

# Convert our severity level into an emoji
def getEmojiFromSeverity(severity):
    severity = severity.lower();
    if (severity == 'info'):        return ':information_source:';
    elif (severity == 'unknown'):   return ':question:';
    elif (severity == 'warning'):   return ':warning:';
    elif (severity == 'error'):     return ':exclamation:';
    else:                           return ':white_check_mark:';

# Default webhook (paste yours here if you want to not have to provide it on the CLI)
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL', "")
SLACK_CHANNEL = os.getenv('SLACK_CHANNEL', "devops")

# Slack message prefix/suffixes
SLACK_MESSAGE_PREFIX = os.getenv('SLACK_MESSAGE_PREFIX', "")
if len(SLACK_MESSAGE_PREFIX) > 0:
     SLACK_MESSAGE_PREFIX = (SLACK_MESSAGE_PREFIX + " ").strip()
SLACK_MESSAGE_SUFFIX = os.getenv('SLACK_MESSAGE_SUFFIX', "")
if len(SLACK_MESSAGE_SUFFIX) > 0:
     SLACK_MESSAGE_SUFFIX = (" " + SLACK_MESSAGE_SUFFIX).strip()

# Usage and CLI opts handling
usage = '  \n\
    %prog "Hi from this slack notifier" \n\
or \n\
    echo "Hi from this slack notifier" | %prog \n\
'


def send(body, username="Kubernetes Volume Autoscaler", severity="info", channel=SLACK_CHANNEL, emoji="", iconurl="https://raw.githubusercontent.com/DevOps-Nirvana/Kubernetes-Volume-Autoscaler/master/icon.png", verbose=False):

    # Skip if not set or set invalidly
    if not SLACK_WEBHOOK_URL or len(SLACK_WEBHOOK_URL) == 0 or SLACK_WEBHOOK_URL == "REPLACEME":
        print("Slack webhook URL not set, skipping")
        return False

    # lowercase our severity since thats our standard
    severity = str(severity).lower()

    # Begin to build our payload
    payload = {
        'username': username + ' - ' + severity.title(),
        'text':     SLACK_MESSAGE_PREFIX + body + SLACK_MESSAGE_SUFFIX,
        'link_names': 1
    }

    # Set our channel, if set, if not it'll usually use the default (general) channel
    if (len(channel)):      payload['channel'] = channel
    # Set our emoji or url if set, but let error take precedence if error is set
    if (severity == 'error'): payload['icon_emoji'] = getEmojiFromSeverity(severity);
    elif (len(emoji)):        payload['icon_emoji'] = emoji
    elif (len(iconurl)):      payload['icon_url'] = iconurl
    else:                     payload['icon_emoji'] = getEmojiFromSeverity(severity);
    # Set verbose
    if verbose:             print("VERBOSE: Payload: \n" + json.dumps(payload, sort_keys=True, indent=4, separators=(',', ': ')))
    # Prefix body if error
    if severity == 'error': payload['text'] = "<!channel> ERROR: " + payload['text']

    # Send the request to Slack
    try:
        rawpayload = json.dumps(payload).encode('utf-8')
        if verbose:         print("VERBOSE: Sending request to " + SLACK_WEBHOOK_URL + "...")
        request = urllib.request.Request(SLACK_WEBHOOK_URL, rawpayload, {'Content-Type': 'application/json', 'Content-Length': len(rawpayload)})
        response = urllib.request.urlopen(request)
        result = response.read()
        result = str(result)
        if ('ok' in result and len(result) < 8):
            if verbose:     print("Sent successfully")
            return True;
        else:
            if verbose:     print("Error while sending: {}".format(result))
            return False;
    except Exception as e:
        if verbose:         print("Error while sending: {}".format(e))
        return False

if __name__ == "__main__":

    parser = OptionParser(usage=usage)
    parser.add_option("-v", "--verbose",
                    action="store_true",
                    dest="verbose",
                    default=False,
                    help="Make lots of noise")
    parser.add_option("-c", "--channel",
                    dest="channel",
                    help="Channel to sent to, use # prefix for private channels",
                    metavar="channel",
                    default="")
    parser.add_option("-u", "--username",
                    dest="username",
                    help="The username this message is coming from",
                    metavar="username",
                    default="Slack Notifier")
    parser.add_option("-s", "--severity",
                    dest="severity",
                    help="The severity of this (info/ok/warning/error/unknown)",
                    metavar="severity",
                    default="info")
    parser.add_option("-e", "--emoji",
                    dest="emoji",
                    help="The emoji to use (overrides iconurl and severity icon)",
                    metavar="emoji",
                    default="")
    parser.add_option("-i", "--iconurl",
                    dest="iconurl",
                    help="The URL to a custom icon (overrides severity icon) ",
                    metavar="iconurl",
                    default="")
    (options, args) = parser.parse_args()

    # Get the message body
    data = getBodyFromSTDIN();
    if ((data != False) and (len(data) > 0)):
        body = data
    elif len(args) > 0:
        body = ' '.join(args)
    else:
        print("ERROR: You MUST pass an argument or pipe STDIN content for the message body")
        parser.print_help()
        exit(1)

    # Fix line endings and double line-endings (a shell/python thing)
    body = body.replace('\r\n', '\r').replace('\n', '\r').replace('\r\r', '\n')
    if options.verbose:     print("VERBOSE: Got body: " + body)

    sent_options = {}
    if len(options.username) > 0:
        sent_options['username'] = options.username
    if len(options.severity) > 0:
        sent_options['severity'] = options.severity
    if len(body) > 0:
        sent_options['body'] = body
    if len(options.channel) > 0:
        sent_options['channel'] = options.channel
    if len(options.emoji) > 0:
        sent_options['emoji'] = options.emoji
    if len(options.iconurl) > 0:
        sent_options['iconurl'] = options.iconurl
    sent_options['verbose'] = options.verbose

    send(**sent_options)
