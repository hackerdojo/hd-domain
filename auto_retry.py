""" Automatically retries requests that failed due to google-API-related
errors. """


import httplib
import logging
import socket
import urllib
import urlparse

import webapp2

from google.appengine.api import taskqueue, urlfetch
from google.appengine.runtime.apiproxy_errors import DeadlineExceededError


""" A function meant to be used as a decorator that automatically makes a
decorated function log any web-related errors and retry the offending action
later.
function: The function to wrap. """
def retry_on_error(function):
  """ A wrapper function. """
  def wrapped(self, *args, **kwargs):
    # Try it and see if it works.
    try:
      return function(self, *args, **kwargs)
    except (httplib.HTTPException, DeadlineExceededError, socket.error) as error:
      logging.exception("Failed to make request, retrying later.")

      _, _, _, query_string, _ = urlparse.urlsplit(self.request.url)
      params = urlparse.parse_qsl(query_string)
      params = {key: value for key, value in params}
      if ("retried" not in params.keys() or not params["retried"]):
        # Mark that we've retried it so that we don't add tasks twice. (It will
        # automatically retry it if it fails.)
        params["retried"] = True

        # Figure out what HTTP action we're using.
        action = self.request.method

        # Add a task for retrying the action.
        taskqueue.add(queue_name="request-retry-queue",
            url=self.request.path, params=params,
            countdown=30, method=action)
      else:
        logging.debug("Not adding a new task for subsequent failure.")

      raise error

  return wrapped
