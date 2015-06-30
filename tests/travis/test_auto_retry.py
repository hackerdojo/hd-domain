""" Tests for the auto_retry functionality. """

# We need our external libraries to be present.
import appengine_config

import httplib
import unittest

import webtest

from google.appengine.ext import testbed
import webapp2

import auto_retry


""" A handler class for testing the decorator. """
class TestHandler(webapp2.RequestHandler):
  @auto_retry.retry_on_error
  def get(self):
    # We can specify whether we want it to fail for testing purposes.
    if self.request.get("fail", False):
      raise httplib.error("This is a test failure.")


""" Test case for the retry_on_error decorator. """
class RetryOnErrorTests(unittest.TestCase):
  """ Set up for every test. """
  def setUp(self):
    # Create and activate testbed instance.
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_taskqueue_stub(root_path=".")

    app = webapp2.WSGIApplication([("/test", TestHandler)])
    self.test_app = webtest.TestApp(app)

    self.task_queue_stub = \
        self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)

  """ Cleanup for every test. """
  def tearDown(self):
    self.testbed.deactivate()

  """ Tests that the decorator retries failed tasks. """
  def test_retry(self):
    response = self.test_app.get("/test", params={"fail": True},
                                 expect_errors=True)
    self.assertEqual(500, response.status_int)

    tasks = self.task_queue_stub.GetTasks("retry-queue")
    self.assertEqual(1, len(tasks))
    # Make sure that our task url looks good.
    good_url = "/test?fail=True&retried=True"
    self.assertEqual(good_url, tasks[0]["url"])
    self.assertEqual("GET", tasks[0]["method"])

  """ Tests that if the task succeeds, it doesn't do anything. """
  def test_success_no_action(self):
    response = self.test_app.get("/test")

    tasks = self.task_queue_stub.GetTasks("retry-queue")
    self.assertEqual(0, len(tasks))

  """ Tests that it doesn't add the task again if there are multiple failures.
  """
  def test_retry_detection(self):
    response = self.test_app.get("/test",
        params={"fail": True, "retried": True}, expect_errors=True)

    tasks = self.task_queue_stub.GetTasks("retry-queue")
    self.assertEqual(0, len(tasks))
