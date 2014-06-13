#!/usr/bin/env python
# -*- coding: utf-8 -*-

import twilio.rest
import switchboard
import argparse

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

HOSTS = {'localhost': 'ws://127.0.0.1:8080/workers'}

# Flip this to True to allow the worker to send push notifications
SEND_APNS = True


class APNSWorker(switchboard.Client):
    """A Switchboard worker that will listen for new emails across all
    accounts. For each new email it wil fetch additional information,
    form it into a push notification, and send it to the client.
    """

    def __init__(self, sid, token, to, from_, *args, **kwargs):
        super(APNSWorker, self).__init__(*args, **kwargs)
        self._to = to
        self._from = from_
        self._twilio = twilio.rest.TwilioRestClient(sid, token)

    def connect(self):
        """Connect to the websocket, and ensure the account is connected and
        the INBOX is being watched, and then start watchingAll.
        """
        super(APNSWorker, self).connect()

        def post_setup((cmds, resps)):
            """Post setup callback."""
            logger.info("Setup complete, listening...")

        self.send_cmds(('watchAll', {})).then(post_setup)

    def received_unsolicited(self, resps):
        def post_fetch((cmds, resps)):
            """Post fetch callback."""
            for msg in resps[0][1]['list']:
                logger.debug("Preparing msg to send: %s", msg)
                from1 = msg['from'][0]
                from_name = from1.get('name') or from1.get('email', '<unknown>')
                notification = "%s - %s" % (from_name, msg['subject'])
                logger.debug("sending text message: %s", notification)
                try:
                    self._twilio.messages.create(
                        body=notification, to=self._to, from_=self._from)
                except Exception as e:
                    logger.error("Error sending push notification: %s", e)
                    raise

        for resp in resps:
            if resp[0] == 'newMessage':
                args = resp[1]
                promise = self.send_cmds(('getMessages',
                                          {'account': args['account'],
                                           'ids': [args['messageId']],
                                           'properties': ['subject', 'from']}))
                promise.then(post_fetch)
            else:
                logger.warning("Unknown unsolicted response: %s", response)



def main(sid, token, to, from_, url):
    """Create, connect, and block on the listener worker."""
    try:
        worker = APNSWorker(sid=sid, token=token, to=to, from_=from_, url=url)
        worker.connect()
        worker.run_forever()
    except KeyboardInterrupt:
        worker.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Loop echo listener")
    parser.add_argument('--host', help="the name of the host (see HOSTS)")
    parser.add_argument('--sid', required=True, help="the twilio sid")
    parser.add_argument('--token', required=True, help="the twilio token")
    parser.add_argument('--to', required=True, help="the destination phone number")
    parser.add_argument('--from', required=True, help="the source phone number")
    args = parser.parse_args()
    main(args.sid, args.token, args.to, getattr(args, 'from'), HOSTS[args.host])
