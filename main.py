import base64
import json
import logging
import os
import sys
import time

from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.api import urlfetch

import webapp2

from domain import Domain
import auto_retry


DOMAIN_ACCOUNT = 'api@hackerdojo.com'


class MainHandler(webapp2.RequestHandler):
  def get(self):
    self.response.out.write("Try /users or /groups ... %s" % users.get_current_user())


class BaseHandler(webapp2.RequestHandler):
  # GAE apps that are allowed to use this API.
  _AUTHORIZED_APPS = ("hd-signup-hrd", "signup-dev", "hd-events-hrd")
  # Names of task queues that are allowed to use this API.
  _AUTHORIZED_QUEUES = ("retry-queue", "__cron")

  """ Meant to be used as a decorator for functions that should only be accessed
  by authorized people and apps. The wrapped function checks the authorization,
  and fails with an error if it is incorrect.
  function: The function we are decorating.
  Returns: A wrapped version of the function that checks authorization. """
  @classmethod
  def restricted(cls, function):
    """ The wrapper function. """
    def wrapper(self, *args, **kwargs):
      app_id = self.request.headers.get("X-Appengine-Inbound-Appid", "None")
      queue_name = self.request.headers.get("X-AppEngine-QueueName", "None")
      logging.debug("Request from app '%s'." % (app_id))
      logging.debug("Request from taskqueue '%s'." % (queue_name))

      if users.is_current_user_admin():
        # Allow admins through, no questions asked.
        logging.info("Allowing admin access.")
      elif "Development" in os.environ["SERVER_SOFTWARE"]:
        # Make an automatic exception if we are running on the local dev server.
        logging.info("Dev server detected. Not restricting access.")
      elif (app_id not in self._AUTHORIZED_APPS and
            queue_name not in self._AUTHORIZED_QUEUES):
        # Unauthorized.
        logging.warning("Denying request from unauthorized source.")
        self.abort(403)

      return function(self, *args, **kwargs)

    return wrapper

  def domain(self):
    return Domain(DOMAIN_ACCOUNT.split('@')[1])


class GroupsHandler(BaseHandler):
  @BaseHandler.restricted
  def get(self):
    groups = self.domain().list_groups()
    self.response.out.write(json.dumps(groups))


class GroupHandler(BaseHandler):
  @BaseHandler.restricted
  def get(self, group_id):
    group = self.domain().get_group_members(group_id)
    self.response.out.write(json.dumps(group))


class UsersHandler(BaseHandler):
  @BaseHandler.restricted
  def get(self):
    users_str = memcache.get('users_str')
    if not users_str:
      users = self.domain().list_users()
      users_str = json.dumps(users)
      memcache.set('users_str', users_str)
    self.response.out.write(users_str)

  """ Add a new user. """
  @auto_retry.retry_on_error
  @BaseHandler.restricted
  def post(self):
    memcache.delete('users_str')

    user = self.domain().add_user(
        username    = self.request.get('username'),
        password    = self.request.get('password'),
        first_name  = self.request.get('first_name'),
        last_name   = self.request.get('last_name'))
    self.response.out.write(json.dumps(user))


class UsersNoCacheHandler(BaseHandler):
  @BaseHandler.restricted
  def get(self):
    users = self.domain().list_users()
    users_str = json.dumps(users)
    memcache.set('users_str', users_str)
    self.response.out.write(users_str)


class SuspendHandler(BaseHandler):
  @auto_retry.retry_on_error
  @BaseHandler.restricted
  def get(self, username):
    self.post(username)

  @auto_retry.retry_on_error
  @BaseHandler.restricted
  def post(self, username):
    memcache.delete('users_str')
    user = self.domain().suspend_user(username)
    self.response.out.write(json.dumps(user))


class RestoreHandler(BaseHandler):
  @auto_retry.retry_on_error
  @BaseHandler.restricted
  def get(self, username):
    self.post(username)

  @auto_retry.retry_on_error
  @BaseHandler.restricted
  def post(self, username):
    memcache.delete('users_str')
    user = self.domain().restore_user(username)
    self.response.out.write(json.dumps(user))


class UserHandler(BaseHandler):
  @BaseHandler.restricted
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
