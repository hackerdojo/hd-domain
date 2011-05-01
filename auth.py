import base64
import urllib
from datetime import datetime
from datetime import timedelta

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

import multipass
from shared import utils

USERVOICE_DOMAIN = 'hackerdojo.uservoice.com'
USERVOICE_API_KEY = '455e26692fd067026ffd74bcdd5d1ef1'
USERVOICE_ACCOUNT = 'hackerdojo'

MULTIPASS_ACCOUNT = 'hackerdojo'
MULTIPASS_API_KEY = 'ec6c2d980724dfcd4e408e58f063fc376f13c8a896f506204c598faf2bc2f5c1c098b928e2e87cc22d373eee0893277314bb8253269176b6fb933bffda01db2e'

class MultipassHandler(webapp.RequestHandler):
    def get(self, action):
        action = urllib.unquote(action)
        to = self.request.GET.get('to')
        if action.startswith('login'):
            user = users.get_current_user()
            if user:
                if ':' in action:
                    action, to = action.split(":")
                    to = base64.b64decode(to)
                    token = multipass.token(dict(email=user.email(), expires=(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S')),
                        api_key=MULTIPASS_API_KEY,
                        account_key=MULTIPASS_ACCOUNT)
                self.redirect("%s?sso=%s" % (to, urllib.quote(token)))
            else:
                to = base64.b64encode(to)
                self.redirect(users.create_login_url('/auth/multipass/login:%s' % to))
        elif action.startswith('logout'):
            user = users.get_current_user()
            if user:
                to = base64.b64encode(to or self.request.referrer)
                self.redirect(users.create_logout_url('/auth/multipass/logout:%s' % to))
            else:
                try:
                    action, to = action.split(":")
                    to = base64.b64decode(to)
                except ValueError:
                    pass
                self.redirect(to)

class UservoiceHandler(webapp.RequestHandler):
    def get(self, action):
        action = urllib.unquote(action)
        to = "http://%s%s" % (USERVOICE_DOMAIN, self.request.GET.get('return', '/'))
        if action.startswith('login'):
            user = users.get_current_user()
            if user:
                if ':' in action:
                    action, to = action.split(":")
                    to = base64.b64decode(to)
                token = multipass.token(dict(guid=user.email(), email=user.email(), display_name=user.email(), expires=(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S')),
                    api_key=USERVOICE_API_KEY,
                    account_key=USERVOICE_ACCOUNT)
                self.redirect("%s?sso=%s" % (to, urllib.quote(token)))
            else:
                to = base64.b64encode(to)
                self.redirect(users.create_login_url('/auth/uservoice/login:%s' % to))
        elif action.startswith('logout'):
            user = users.get_current_user()
            if user:
                to = base64.b64encode(to or self.request.referrer)
                self.redirect(users.create_logout_url('/auth/uservoice/logout:%s' % to))
            else:
                try:
                    action, to = action.split(":")
                    to = base64.b64decode(to)
                except ValueError:
                    pass
                self.redirect(to)


def main():
    application = webapp.WSGIApplication([
        ('/auth/login', utils.Redirect(users.create_login_url('/'))),
        ('/auth/logout', utils.Redirect(users.create_logout_url('/'))),
        ('/auth/multipass/(.+)', MultipassHandler),
        ('/auth/uservoice/(.+)', UservoiceHandler),
        ],debug=True)
    run_wsgi_app(application)

if __name__ == '__main__':
    main()
