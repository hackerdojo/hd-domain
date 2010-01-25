#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.api import urlfetch
from django.utils import simplejson
import gdata.apps.service
from google.appengine.api import memcache
import logging, urllib

def flatten(l):
    out = []
    for item in l:
        if isinstance(item, (list, tuple)):
            out.extend(flatten(item))
        else:
            out.append(item)
    return out

class MainHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write("Nothing here")

class UsersHandler(webapp.RequestHandler):
    def get(self):
        client = gdata.apps.service.AppsService(domain='hackerdojo.com')
        token = memcache.get('token')
        if token:
            client.SetClientLoginToken(token)
            self.response.out.write(simplejson.dumps(
                [e.title.text for e in flatten([u.entry for u in client.GetGeneratorForAllUsers()])]))
        else:
            request_token_key()
            self.response.set_status(503)
            self.response.out.write("Refreshing token. Please try again.")
        

class TokenFetchHandler(webapp.RequestHandler):
    def get(self):
        self.post()
        
    def post(self):
        password = self.request.get('key')
        if password:
            client = gdata.apps.service.AppsService(domain='hackerdojo.com')
            client.ClientLogin('jeff@hackerdojo.com', password)
            token = client.GetClientLoginToken()
            if not memcache.add('token', token, 3600*24):
                logging.error("Memcache set failed.")
            else:
                logging.info('Token fetched: %s' % token)
        else:
            request_token_key()
            
def request_token_key():
    urlfetch.fetch('http://www.thekeymaster.org/f052e1e1640752cbd83630226dfe311b', method='POST', payload=urllib.urlencode({'secret': '4awrfzvz'}))

def main():
    application = webapp.WSGIApplication([
        ('/', MainHandler),
        ('/users', UsersHandler),
        ('/token/fetch', TokenFetchHandler),
        ],debug=True)
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()
