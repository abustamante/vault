# -*- coding:utf-8 -*-

from unittest import TestCase
from mock import patch

from vault.tests.fakes import fake_request
from dashboard.views import DashboardView


class DashboardTest(TestCase):


    def setUp(self):
        self.view = DashboardView.as_view()

        self.request = fake_request(method='GET')
        self.request.user.is_authenticated = lambda: True

    def tearDown(self):
        patch.stopall()

    @patch('dashboard.views.ProjectGroups.objects.filter')
    def test_check_projects_in_context(self, mock_projects):

        mock_projects.return_value = []

        template = self.view(self.request)

        self.assertEqual(template.context_data['projects'], [])

    # def test_dashboard_will_redirect_to_login_if_not_logged(self):
    #     self.request.method = 'POST'
    #     self.request.build_absolute_uri = lambda: '/'
    #     self.request.user.is_authenticated = lambda: False

    #     response = self.view(self.request)

    #     self.assertEqual(response.status_code, 302)
