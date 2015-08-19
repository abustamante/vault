# -*- coding:utf-8 -*-

from unittest import TestCase

from mock import Mock, patch

from identity.keystone import Keystone
from identity.tests.fakes import FakeResource, FakeToken
from identity.views import ListProjectView, CreateProjectView, UpdateProjectView
from vault.tests.fakes import fake_request


class ListProjectTest(TestCase):

    def setUp(self):
        self.view = ListProjectView.as_view()
        self.request = fake_request(method='GET')

        patch('identity.keystone.Keystone._keystone_conn',
              Mock(return_value=None)).start()

    def tearDown(self):
        patch.stopall()

    def test_list_projects_needs_authentication(self):
        response = self.view(self.request)
        self.assertEqual(response.status_code, 302)

    def test_show_project_list(self):
        patch('identity.keystone.Keystone.project_list',
              Mock(return_value=[FakeResource(1)])).start()

        self.request.user.is_authenticated = lambda: True
        self.request.user.is_superuser = True
        # self.request.user.token = FakeToken

        response = self.view(self.request)
        response.render()

        self.assertIn('<td>FakeResource1</td>', response.content)

    @patch('identity.keystone.Keystone.project_list')
    def test_list_project_view_exception(self, mock_project_list):
        mock_project_list.side_effect = Exception()

        self.request.user.is_authenticated = lambda: True
        self.request.user.is_superuser = True

        response = self.view(self.request)
        msgs = [msg for msg in self.request._messages]

        self.assertGreater(len(msgs), 0)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(msgs[0].message, 'Unable to list projects')


class CreateProjectTest(TestCase):

    def setUp(self):
        self.view = CreateProjectView.as_view()

        self.request = fake_request(method='GET')
        self.request.META.update({
            'SERVER_NAME': 'globo.com',
            'SERVER_PORT': '80'
        })
        self.request.user.is_superuser = True
        self.request.user.is_authenticated = lambda: True
        # self.request.user.token = FakeToken

        patch('actionlogger.ActionLogger.log',
              Mock(return_value=None)).start()

        patch('identity.keystone.Keystone._keystone_conn',
              Mock(return_value=None)).start()

    def tearDown(self):
        patch.stopall()

    def test_create_project_needs_authentication(self):
        self.request.user.is_authenticated = lambda: False
        # self.request.user.token = None

        response = self.view(self.request)

        self.assertEqual(response.status_code, 302)

    def test_enabled_field_is_a_select_tag(self):
        from django.forms.widgets import Select
        enabled_field = CreateProjectView.form_class.base_fields['enabled']

        self.assertIsInstance(enabled_field.widget, Select)

    def test_ensure_enabled_field_initial_value_is_true(self):
        enabled_field = CreateProjectView.form_class.base_fields['enabled']

        self.assertTrue(enabled_field)

    def test_validating_description_field_blank(self):
        project = FakeResource(1, 'project1')
        project.to_dict = lambda: {
            'name': project.name,
            'description': project.description
        }

        patch('identity.keystone.Keystone.project_get',
              Mock(return_value=project)).start()

        self.request.method = 'POST'

        post = self.request.POST.copy()
        post.update({
            'name': 'Project1',
            'enabled': True,
            'id': 1,
            'description': ''})
        self.request.POST = post

        response = self.view(self.request)
        response.render()

        self.assertIn('This field is required', response.content)

    def test_validating_name_field_blank(self):
        project = FakeResource(1, 'project1')
        project.to_dict = lambda: {
            'name': project.name,
            'description': project.description
        }

        patch('identity.keystone.Keystone.project_get',
              Mock(return_value=project)).start()

        self.request.method = 'POST'

        post = self.request.POST.copy()
        post.update({
            'name': '',
            'enabled': True,
            'id': 1,
            'description': 'description'})
        self.request.POST = post

        response = self.view(self.request)
        response.render()

        self.assertIn('This field is required', response.content)

    @patch('identity.keystone.Keystone.project_create')
    def test_project_create_method_was_called(self, mock):

        self.request.method = 'POST'
        post = self.request.POST.copy()

        post.update({'name': 'aaa', 'enabled': True, 'description': 'desc'})
        self.request.POST = post

        response = self.view(self.request)

        mock.assert_called_with(self.request, 'aaa', enabled=True, description='desc')

    @patch('identity.keystone.Keystone.project_create')
    def test_project_create_view_exception(self, mock_project_create):
        mock_project_create.side_effect = Exception()

        self.request.method = 'POST'
        post = self.request.POST.copy()
        post.update({'name': 'aaa', 'enabled': True, 'description': 'desc'})
        self.request.POST = post

        response = self.view(self.request)
        msgs = [msg for msg in self.request._messages]

        self.assertGreater(len(msgs), 0)
        self.assertEqual(msgs[0].message, 'Error when create project')


class UpdateProjectTest(TestCase):

    def setUp(self):
        self.view = UpdateProjectView.as_view()

        self.request = fake_request()
        self.request.META.update({
            'SERVER_NAME': 'globo.com',
            'SERVER_PORT': '80'
        })
        self.request.user.is_superuser = True
        self.request.user.is_authenticated = lambda: True
        # self.request.user.token = FakeToken

        patch('actionlogger.ActionLogger.log',
              Mock(return_value=None)).start()

        patch('identity.keystone.Keystone._keystone_conn',
              Mock(return_value=None)).start()

    def tearDown(self):
        patch.stopall()

    @patch('identity.keystone.settings', KEYSTONE_VERSION=2)
    @patch('identity.keystone.Keystone._keystone_conn')
    def test_project_manager_v2(self, mock_keystone_conn, mock_settings):
        conn = Keystone(self.request)
        response = conn._project_manager()

        self.assertIn('tenants', str(response))

    # @patch('identity.keystone.settings', KEYSTONE_VERSION=3)
    # @patch('identity.keystone.Keystone._keystone_conn')
    # def test_project_manager_v3(self, mock_keystone_conn, mock_settings):
    #     conn = Keystone(self.request)
    #     response = conn._project_manager()
    #
    #     self.assertIn('projects', str(response))

    @patch('identity.keystone.Keystone.project_update')
    def test_project_update_method_was_called(self, mock):

        project = FakeResource(1, 'project1')
        project.to_dict = lambda: {'name': project.name}
        project.default_project_id = 1

        patch('identity.keystone.Keystone.project_get',
              Mock(return_value=project)).start()

        self.request.method = 'POST'

        post = self.request.POST.copy()
        post.update({'name': 'bbb', 'enabled': True,
                     'description': 'desc', 'id': 1})
        self.request.POST = post

        response = self.view(self.request)

        mock.assert_called_with(project, enabled=True, description='desc',
                                name='bbb')
