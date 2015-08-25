# -*- coding:utf-8 -*-

from unittest import TestCase
from mock import patch
from keystoneclient.openstack.common.apiclient import exceptions

from django.conf import settings

from identity.keystone import Keystone, UnauthorizedProject
from identity.tests.fakes import UserFactory, ProjectFactory, GroupFactory, FakeResource, AreaFactory
from vault.tests.fakes import fake_request


class TestKeystoneV2(TestCase):
    """ Test keystone version 2 """

    def setUp(self):
        self.user = UserFactory()
        self.request = fake_request(user=self.user)

        project_id = 'abcdefghiklmnopq'
        project_name = 'project_test'
        project_desc = 'project description'

        self.project = ProjectFactory(id=project_id, name=project_name, description=project_desc)
        self.mock_project_create = patch('identity.keystone.Keystone.project_create').start()
        self.mock_project_create.return_value = self.project

        self.mock_project_update = patch('identity.keystone.Keystone.project_update').start()
        self.mock_project_update.return_value = self.project

        fake_project = FakeResource(n='abcdefg', name='fake_project')
        fake_project.description = 'desc do fake'

        self.mock_project_get = patch('identity.keystone.Keystone.project_get').start()
        self.mock_project_get.return_value = fake_project

        self.mock_keystone_is_allowed = patch('identity.keystone.Keystone._is_allowed_to_connect').start()
        self.mock_keystone_conn = patch('identity.keystone.Keystone._keystone_conn').start()

        self.group = GroupFactory(id=1)
        self.area = AreaFactory(id=1)

    def tearDown(self):
        self.mock_project_get.stop()
        self.mock_project_create.stop()

        self.mock_keystone_conn.stop()
        self.mock_keystone_is_allowed.stop()

        patch.stopall()

    @patch('identity.keystone.Keystone.user_create')
    @patch('identity.keystone.Keystone.create_password')
    @patch('identity.keystone.AreaProjects')
    @patch('identity.keystone.GroupProjects')
    def test_vault_create_project(self, mock_gp, mock_ap, mock_key_pass, mock_key_user):

        mock_key_user.return_value = FakeResource(n=self.project.id, name='u_{}'.format(self.project.name))
        mock_key_pass.return_value = 'password'

        keystone = Keystone(self.request, 'tenant_name')

        expected = {
            'status': True,
            'project': self.mock_project_create.return_value,
            'user': mock_key_user.return_value,
            'password': mock_key_pass.return_value,
        }

        computed = keystone.vault_create_project(self.project.name, 1, 1, description=self.project.description)

        # Criacao do Project
        self.mock_project_create.assert_called_with(self.project.name, description=self.project.description, enabled=True)

        # Criacao do User
        mock_key_user.assert_called_with(name='u_{}'.format(self.project.name),
                                         password='password',
                                         project=self.project.id,
                                         role=settings.ROLE_BOLADONA)

        mock_gp.assert_called_with(group_id=1, project_id=self.project.id)
        self.assertTrue(mock_gp.return_value.save.called)

        mock_ap.assert_called_with(area_id=1, project_id=self.project.id)
        self.assertTrue(mock_gp.return_value.save.called)

        self.assertEqual(computed, expected)

    @patch('identity.keystone.Keystone.user_create')
    def test_vault_create_project_forbidden_on_project_create(self, mock_key_user):

        self.mock_project_create.side_effect = exceptions.Forbidden
        mock_key_user.return_value = FakeResource(n=self.project.id, name='u_{}'.format(self.project.name))

        keystone = Keystone(self.request, 'tenant_name')

        expected = {'status': False, 'reason': 'Admin required'}
        computed = keystone.vault_create_project(self.project.name, 1, 1, description=self.project.description)

        self.assertEqual(computed, expected)

        # Criacao de user nao pode ocorrer quando hover falha na criacao do project
        self.assertFalse(mock_key_user.called)

    @patch('identity.keystone.Keystone.project_create')
    @patch('identity.keystone.Keystone.project_delete')
    @patch('identity.keystone.Keystone.user_create')
    def test_vault_create_project_forbidden_on_user_create(self, mock_key_user, mock_project_delete, mock_project_create):

        mock_project_create.return_value = ProjectFactory(id=self.project.id, name=self.project.name)
        mock_key_user.side_effect = exceptions.Forbidden

        keystone = Keystone(self.request, 'tenant_name')

        expected = {'status': False, 'reason': 'Admin required'}
        computed = keystone.vault_create_project(self.project.name, 1, 1, description=self.project.description)

        self.assertEqual(computed, expected)

        # Se falhou o cadastro de usuario, o project devera ser deletado
        mock_project_delete.assert_called_with(self.project.id)

    @patch('identity.keystone.Keystone.project_delete')
    @patch('identity.keystone.Keystone.user_create')
    @patch('identity.keystone.Keystone.user_delete')
    @patch('identity.keystone.GroupProjects.save')
    def test_vault_create_project_fail_to_save_group_project_on_db(self, mock_gp_save, mock_user_delete, mock_user_create, mock_project_delete):

        fake_user = FakeResource(n=self.project.id, name='u_{}'.format(self.project.name))

        mock_user_create.return_value = fake_user

        # Excecao ao salvar no db
        mock_gp_save.side_effect = Exception

        keystone = Keystone(self.request, 'tenant_name')

        expected = {'status': False, 'reason': 'Unable to assign project to group'}
        computed = keystone.vault_create_project(self.project.name, 1, 1, description=self.project.description)

        self.assertEqual(computed, expected)

        mock_project_delete.assert_called_with(self.project.id)

        mock_user_delete.assert_called_with(fake_user.id)

    @patch('identity.keystone.AreaProjects')
    @patch('identity.keystone.GroupProjects.save')
    @patch('identity.keystone.Keystone.project_delete')
    @patch('identity.keystone.Keystone.user_create')
    @patch('identity.keystone.Keystone.user_delete')
    def test_vault_create_project_fail_to_save_project_to_team_on_db(self, mock_user_delete, mock_user_create, mock_project_delete, _, mock_areaprojects):
        mock_areaprojects.side_effect = Exception

        project_name = 'project_test'

        fake_user = FakeResource(n=self.project.id, name='u_{}'.format(self.project.name))

        mock_user_create.return_value = fake_user

        keystone = Keystone(self.request, 'tenant_name')
        result = keystone.vault_create_project(project_name, self.group, self.area)
        expected = {'status': False, 'reason': 'Unable to assign project to area'}
        self.assertEqual(result, expected)

        mock_project_delete.assert_called_with(self.project.id)
        mock_user_delete.assert_called_with(fake_user.id)

        # FALTA LIMPAR AREAGROUP

    def test_create_password(self):

        computed = Keystone.create_password()

        self.assertTrue(isinstance(computed, str))

    @patch('identity.keystone.Keystone.user_list')
    @patch('identity.keystone.Keystone.project_get')
    def test_return_find_u_user(self, mock_project_get, mock_user_list):
        mock_project_get.return_value = ProjectFactory(id='abcde', name='infra')
        mock_user_list.return_value = UserFactory(id='abcde', username='u_project_test')

        keystone = Keystone(self.request, 'tenant_id')

        fake_user = 'u_{}'.format(self.project.name)
        self.assertEqual(fake_user, mock_user_list.return_value.username)

    @patch('identity.keystone.AreaProjects')
    @patch('identity.keystone.GroupProjects')
    def test_vault_update_project(self, mock_gp, mock_ap):

        group_id = 123
        area_id = 456

        keystone = Keystone(self.request, 'tenant_name')

        fake_project = self.mock_project_get.return_value

        expected = {
            'status': True,
            'project': self.mock_project_update.return_value,
        }

        computed = keystone.vault_update_project(self.project.id,
                                           self.project.name,
                                           group_id,
                                           area_id,
                                           description=self.project.description)

        # Update do Project
        self.mock_project_update.assert_called_with(fake_project,
                                                    name=self.project.name,
                                                    description=self.project.description,
                                                    enabled=True)

        mock_gp.objects.filter.assert_called_with(project_id=self.project.id)
        self.assertTrue(mock_gp.objects.filter.return_value.delete.called)

        mock_gp.assert_called_with(group_id=group_id, project_id=self.project.id)
        self.assertTrue(mock_gp.return_value.save.called)

        mock_ap.objects.filter.assert_called_with(project_id=self.project.id)
        self.assertTrue(mock_ap.objects.filter.return_value.delete.called)

        mock_ap.assert_called_with(area_id=area_id, project_id=self.project.id)
        self.assertTrue(mock_ap.return_value.save.called)

        # self.assertEqual(computed, expected)


class TestKeystonePermissionToConnect(TestCase):
    """
    This tests are separated because it can't mock mock_keystone_is_allowed
    method
    """

    def setUp(self):
        self.request = fake_request()

        self.mock_filter = patch('identity.keystone.GroupProjects.objects.filter').start()

        self.mock_model_project_get = patch('identity.keystone.Project.objects.get').start()
        self.mock_model_project_get.return_value = ProjectFactory()

        self.mock_keystone_conn = patch('identity.keystone.Keystone._keystone_conn').start()

    def tearDown(self):
        self.mock_keystone_conn.stop()
        patch.stopall()

    def test_superuser_creates_keystone_conn(self):
        self.mock_filter.return_value = None
        self.conn = Keystone(self.request, 'tenant_id')
        self.assertTrue(isinstance(self.conn, Keystone))

    def test_regular_user_creates_keystone_conn_on_a_allowed_project(self):

        # Se este mock retorna uma lista nao vazia, significa que o time do project
        # usuario possui permissao no project
        self.mock_filter.return_value = [1]

        self.request.user.is_superuser = False
        self.conn = Keystone(self.request, 'tenant_id')

        self.assertTrue(isinstance(self.conn, Keystone))

    def test_regular_user_creates_keystone_conn_on_a_NOT_allowed_project(self):

        # Se este mock retorna uma lista  vazia, significa que o time do project
        # usuario NAO possui permissao no project
        self.mock_filter.return_value = []
        self.request.user.is_superuser = False

        self.assertRaises(UnauthorizedProject, Keystone, self.request, 'tenant_id')