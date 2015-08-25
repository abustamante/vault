# -*- coding:utf-8 -*-

import logging

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic.base import View, TemplateView
from django.views.generic.edit import FormView

from django.views.decorators.debug import sensitive_post_parameters

from keystoneclient.exceptions import Conflict

from actionlogger import ActionLogger
from identity.keystone import Keystone
from identity.forms import UserForm, CreateUserForm, UpdateUserForm, ProjectForm

from vault import utils
from vault.models import GroupProjects, AreaProjects
from vault.views import SuperUserMixin, JSONResponseMixin, LoginRequiredMixin


log = logging.getLogger(__name__)
actionlog = ActionLogger()


class ListUserView(SuperUserMixin, TemplateView):
    template_name = "identity/users.html"

    def get_context_data(self, **kwargs):
        context = super(ListUserView, self).get_context_data(**kwargs)
        keystone = Keystone(self.request)
        page = self.request.GET.get('page', 1)

        try:
            users = sorted(keystone.user_list(), key=lambda l: l.name.lower())
            context['users'] = utils.generic_pagination(users, page)
        except Exception as e:
            log.exception('Exception: %s' % e)
            messages.add_message(self.request, messages.ERROR,
                                 "Unable to list users")

        return context


class BaseUserView(SuperUserMixin, FormView):
    form_class = UserForm
    success_url = reverse_lazy('users')

    def __init__(self):
        self.keystone = None

    def _fill_project_choices(self, form):
        if self.keystone and 'project' in form.fields:
            items = [('', '---')]

            for i in self.keystone.project_list():
                if getattr(i, 'enabled', None):
                    items.append((i.id, i.name))

            form.fields['project'].choices = items

    def _fill_role_choices(self, form):
        if self.keystone and 'role' in form.fields:
            items = [('', '---')]

            for i in self.keystone.role_list():
                items.append((i.id, i.name))

            form.fields['role'].choices = items

    @method_decorator(sensitive_post_parameters('password', 'password_confirm'))
    def dispatch(self, *args, **kwargs):
        return super(BaseUserView, self).dispatch(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        self.keystone = Keystone(request)
        form = self.get_form(self.form_class)

        self._fill_project_choices(form)
        self._fill_role_choices(form)

        return self.render_to_response(
            self.get_context_data(form=form, **kwargs)
        )

    def get_context_data(self, **kwargs):
        context = super(BaseUserView, self).get_context_data(**kwargs)
        user_id = kwargs.get('user_id')
        form = kwargs.get('form')

        if not user_id:
            user_id = form.data.get('id')

        if user_id:
            user = self.keystone.user_get(user_id)
            form.initial = user.to_dict()
            form.fields['project'].initial = user.project_id
            context['user_id'] = user_id

        return context


class CreateUserView(BaseUserView):
    form_class = CreateUserForm
    template_name = "identity/user_create.html"

    def post(self, request, *args, **kwargs):
        self.keystone = Keystone(self.request)
        form = self.get_form(self.form_class)

        self._fill_project_choices(form)
        self._fill_role_choices(form)

        if form.is_valid():
            post = request.POST

            enabled = False if post.get('enabled') in ('False', '0') else True

            try:
                user = self.keystone.user_create(name=post.get('name'),
                    email=post.get('email'), password=post.get('password'),
                    project=post.get('project'), enabled=enabled,
                    domain=post.get('domain'), role=post.get('role'))

                messages.add_message(request, messages.SUCCESS,
                                     'Successfully created user')
                actionlog.log(request.user.username, 'create', user)

            except Exception as e:
                log.exception('Exception: %s' % e)
                messages.add_message(request, messages.ERROR,
                                     'Error when create user')

            return self.form_valid(form)
        else:
            return self.form_invalid(form)


class UpdateUserView(BaseUserView):
    form_class = UpdateUserForm
    template_name = "identity/user_edit.html"

    def post(self, request, *args, **kwargs):
        self.keystone = Keystone(self.request)
        form = self.get_form(self.form_class)

        self._fill_project_choices(form)

        if form.is_valid():
            post = request.POST
            enabled = False if post.get('enabled') in ('False', '0') else True

            try:
                user = self.keystone.user_get(post.get('id'))

                # can't modify primary project
                project = self.keystone.project_get(user.project_id)

                self.keystone.user_update(user, name=post.get('name'),
                    email=post.get('email'), password=post.get('password'),
                    project=project, enabled=enabled, domain=post.get('domain'))

                messages.add_message(request, messages.SUCCESS,
                                     'Successfully updated user')
                actionlog.log(request.user.username, 'update', user)

            except Exception as e:
                log.exception('Exception: %s' % e)
                messages.add_message(request, messages.ERROR,
                                     'Error when update user')

            return self.form_valid(form)
        else:
            return self.form_invalid(form)


class DeleteUserView(BaseUserView):

    def get(self, request, *args, **kwargs):
        self.keystone = Keystone(request)

        try:
            self.keystone.user_delete(kwargs.get('user_id'))
            messages.add_message(request, messages.SUCCESS,
                                 'Successfully deleted user')
            actionlog.log(request.user.username, 'delete',
                          'user_id: %s' % kwargs.get('user_id'))

            user = self.keystone.user_get(kwargs.get('user_id'))

        except Exception as e:
            log.exception('Exception: %s' % e)
            messages.add_message(request, messages.ERROR,
                                 'Error when delete user')

        return HttpResponseRedirect(self.success_url)


class BaseProjectView(LoginRequiredMixin, FormView):
    success_url = reverse_lazy('projects')

    def __init__(self):
        self.keystone = None

    def get(self, request, *args, **kwargs):

        form = ProjectForm(initial={'user': request.user})
        context = self.get_context_data(form=form, request=request, **kwargs)

        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        request = kwargs.get('request')
        context = super(BaseProjectView, self).get_context_data(**kwargs)
        project_id = kwargs.get('project_id')
        form = kwargs.get('form')

        # Mostra a gerencia de roles qd for superuser acessando admin
        context['show_roles'] = request.user.is_superuser and \
                                request.path[0:15] == '/admin/project/'

        if not project_id:
            project_id = form.data.get('id')

        if project_id:

            self.keystone = Keystone(request)
            project = self.keystone.project_get(project_id)
            form.initial = project.to_dict()

            group_project = GroupProjects.objects.get(project_id=project_id)
            area_project = AreaProjects.objects.get(project_id=project_id)

            form.initial['groups'] = group_project.group_id
            form.initial['areas'] = area_project.area_id

            context['idendity_project_id'] = project_id
            context['has_id'] = True

            if context['show_roles']:

                try:
                    users = self.keystone.user_list()
                    context['users'] = sorted(users, key=lambda l: l.name.lower())

                    roles = self.keystone.role_list()
                    context['roles'] = sorted(roles, key=lambda l: l.name.lower())
                except Exception as e:
                    log.exception('Exception: %s' % e)

        return context


class ListProjectView(BaseProjectView):
    template_name = "identity/projects.html"

    def get_context_data(self, **kwargs):
        context = super(ListProjectView, self).get_context_data(**kwargs)
        keystone = Keystone(self.request)
        page = self.request.GET.get('page', 1)

        try:
            projects = sorted(keystone.project_list(),
                                key=lambda l: l.name.lower())
            context['projects'] = utils.generic_pagination(projects, page)
        except Exception as e:
            log.exception('Exception: %s' % e)
            messages.add_message(self.request, messages.ERROR,
                                 "Unable to list projects")

        return context


# class CreateProjectViewOriginal(BaseProjectView):
#     template_name = "identity/project_create.html"
#
#     def post(self, request, *args, **kwargs):
#         self.keystone = Keystone(request)
#         form = ProjectForm(request.user)
#
#         if form.is_valid():
#             post = request.POST
#             enabled = False if post.get('enabled') in ('False', '0') else True
#             description = post.get('description')
#
#             if description == '':
#                 description = None
#
#             try:
#                 project = self.keystone.project_create(request,
#                                                        post.get('name'),
#                                                        description=description,
#                                                        enabled=enabled)
#
#                 messages.add_message(request, messages.SUCCESS,
#                                      'Successfully created project')
#
#                 actionlog.log(request.user.username, 'create', project)
#             except Exception as e:
#                 log.exception('Exception: %s' % e)
#                 messages.add_message(request, messages.ERROR,
#                                      "Error when create project")
#
#             audit = Audit(user=request.user.username, action=Audit.ADD, item=Audit.PROJECT + ' - ' + post.get('name'), through=Audit.VAULT + ' - ' + Audit.IDENTITY, created_at=Audit.NOW)
#             actionlog.savedb(audit)
#
#             return self.form_valid(form)
#         else:
#             return self.form_invalid(form)


class CreateProjectView(BaseProjectView):
    template_name = "identity/project_create.html"
    form_class = ProjectForm
    success_url = reverse_lazy('projects')

    def post(self, request, *args, **kwargs):
        form = ProjectForm(initial={'user': request.user}, data=request.POST)

        if form.is_valid():
            keystone = Keystone(request)
            post = request.POST
            description = post.get('description')

            if description == '':
                description = None

            try:
                project = keystone.vault_create_project(post.get('name'),
                                                        post.get('groups'),
                                                        post.get('areas'),
                                                        description=description)

                messages.add_message(request, messages.SUCCESS,
                                     'Successfully created project')

                actionlog.log(request.user.username, 'create', project)

            except Exception as e:
                log.exception('Exception: %s' % e)
                messages.add_message(request, messages.ERROR,
                                     "Error when create project")

            return self.form_valid(form)
        else:
            # return self.form_invalid(form)
            return self.render_to_response(self.get_context_data(form=form, request=request))


class UpdateProjectView(BaseProjectView):
    template_name = "identity/project_edit.html"

    def post(self, request, *args, **kwargs):

        form = ProjectForm(initial={'user': request.user}, data=request.POST)

        post = request.POST
        if form.is_valid():
            keystone = Keystone(self.request)
            enabled = False if post.get('enabled') in ('False', '0') else True
            description = post.get('description')
            group_id = post.get('groups')
            area_id = post.get('areas')
            desc = post.get('description')
            enabled = post.get('enabled')

            if description == '':
                description = None

            try:
                project = keystone.project_get(post.get('id'))
                keystone.vault_update_project(project.id, project.name,
                                               group_id, area_id, description=desc,
                                               enabled=enabled)

                messages.add_message(request, messages.SUCCESS,
                                     'Successfully updated project')

                actionlog.log(request.user.username, 'update', project)

            except Exception as e:
                log.exception('Exception: %s' % e)
                messages.add_message(request, messages.ERROR,
                                     "Error when update project")

            return self.form_valid(form)
        else:
            # return self.form_invalid(form)
            return self.render_to_response(self.get_context_data(form=form, request=request))


class DeleteProjectView(BaseProjectView):

    def get(self, request, *args, **kwargs):
        self.keystone = Keystone(request)

        try:
            self.keystone.project_delete(kwargs.get('project_id'))
            messages.add_message(request, messages.SUCCESS,
                                 'Successfully deleted project')

            actionlog.log(request.user.username, 'delete', 'project_id: %s' % kwargs.get('project_id'))

        except Exception as e:
            log.exception('Exception: %s' % e)
            messages.add_message(request, messages.ERROR,
                                 'Error when delete project')

            project = self.keystone.project_get(kwargs.get('project_id'))

        return HttpResponseRedirect(self.success_url)


class ListUserRoleView(SuperUserMixin, View, JSONResponseMixin):

    def post(self, request, *args, **kwargs):
        self.keystone = Keystone(request)
        project_id = request.POST.get('project')
        context = {}

        try:
            project_users = self.keystone.user_list(project=project_id)

            context['users'] = []
            unique_users = set()

            for user in project_users:
                if user.username not in unique_users:
                    unique_users.add(user.username)
                    context['users'].append({
                        'id': user.id,
                        'username': user.username,
                        'roles': self.get_user_roles(user, project_id)
                    })

            return self.render_to_response(context)

        except Exception as e:
            context['msg'] = 'Error listing users'
            log.exception('Exception: %s' % e)

            return self.render_to_response(context, status=500)

    def get_user_roles(self, user, project_id):
        # TODO: in v3 client users won't list roles (verify role_assignments)
        return [{'id': r.id, 'name': r.name}
                for r in user.list_roles(project_id)]


class AddUserRoleView(SuperUserMixin, View, JSONResponseMixin):

    def post(self, request, *args, **kwargs):
        self.keystone = Keystone(request)

        project = request.POST.get('project')
        role = request.POST.get('role')
        user = request.POST.get('user')

        context = {'msg': 'ok'}

        try:
            self.keystone.add_user_role(project=project, role=role, user=user)

            actionlog.log(request.user.username, 'create', 'project: %s, role: %s, user: %s' % (project, role, user))

            return self.render_to_response(context)

        except Conflict as e:
            context['msg'] = 'User already registered with this role'
            log.exception('Conflict: %s' % e)
            return self.render_to_response(context, status=500)

        except Exception as e:
            context['msg'] = 'Error adding user'
            log.exception('Exception: %s' % e)
            return self.render_to_response(context, status=500)


class DeleteUserRoleView(SuperUserMixin, View, JSONResponseMixin):

    def post(self, request, *args, **kwargs):
        self.keystone = Keystone(request)

        project = request.POST.get('project')
        role = request.POST.get('role')
        user = request.POST.get('user')

        context = {'msg': 'ok'}

        try:
            self.keystone.remove_user_role(project=project, role=role, user=user)

            actionlog.log(request.user.username, 'delete', 'project: %s, role: %s, user: %s' % (project, role, user))

            return self.render_to_response(context)

        except Exception as e:
            context['msg'] = 'Error removing user'
            log.exception('Exception: %s' % e)
            return self.render_to_response(context, status=500)
