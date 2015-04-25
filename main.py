import base64
import json
import logging
import sys
import time

from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.api import urlfetch

import webapp2

from domain import Domain


DOMAIN_ACCOUNT = 'api@hackerdojo.com'


class MainHandler(webapp2.RequestHandler):
    def get(self):
        self.response.out.write("Try /users or /groups ... %s" % users.get_current_user())


class BaseHandler(webapp2.RequestHandler):
    def domain(self):
        return Domain(DOMAIN_ACCOUNT.split('@')[1])


class GroupsHandler(BaseHandler):
    def get(self):
        groups = self.domain().list_groups()
        self.response.out.write(json.dumps(groups))


class GroupHandler(BaseHandler):
    def get(self, group_id):
        group = self.domain().get_group(group_id)
        self.response.out.write(json.dumps(group))


class UsersHandler(BaseHandler):
    def get(self):
        users_str = memcache.get('users_str')
        if not users_str:
            users = self.domain().list_users()
            users_str = json.dumps(users)
            memcache.set('users_str', users_str)
        self.response.out.write(users_str)

    def post(self):
        if self.secure():
            memcache.delete('users_str')

            user = self.domain().add_user(
                username    = self.request.get('username'),
                password    = self.request.get('password'),
                first_name  = self.request.get('first_name'),
                last_name   = self.request.get('last_name'))
            self.response.out.write(json.dumps(user))


class UsersNoCacheHandler(BaseHandler):
    def get(self):
        users = self.domain().list_users()
        users_str = json.dumps(users)
        memcache.set('users_str', users_str)
        self.response.out.write(users_str)


class SuspendHandler(BaseHandler):
    def get(self, username):
        self.post(username)

    def post(self, username):
        memcache.delete('users_str')
        user = self.domain().suspend_user(username)
        self.response.out.write(json.dumps(user))


class RestoreHandler(BaseHandler):
    def get(self, username):
        self.post(username)

    def post(self, username):
        memcache.delete('users_str')
        user = self.domain().restore_user(username)
        self.response.out.write(json.dumps(user))


class UserHandler(BaseHandler):
    def get(self, username):
        user = self.domain().get_user(username)
        self.response.out.write(json.dumps(user))


app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/restore/(.+)', RestoreHandler),
    ('/suspend/(.+)', SuspendHandler),
    ('/users_nocache', UsersNoCacheHandler),
    ('/users', UsersHandler),
    ('/users/(.+)', UserHandler),
    ('/groups', GroupsHandler),
    ('/groups/(.+)', GroupHandler),
    ],debug=True)
