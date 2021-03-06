# -*- coding: utf-8 -*-

from django import template
from django.conf import settings


register = template.Library()


@register.tag
def render_widgets(parser, token):
    """
    Renderiza todos os widgets registrados em settings.DASHBOARD_WIDGETS
    """
    return RenderWidgets()


class RenderWidgets(template.Node):

    def render(self, context):
        content = ['<ul class="dashboard-widgets">']

        for item in settings.DASHBOARD_WIDGETS:
            WidgetClass = self._get_widget_cls(item)
            widget = WidgetClass(context)
            content.append(widget.render())

        content = '{}</ul>'.format(''.join(content).encode('ISO-8859-1'))

        return content

    def _get_widget_cls(self, cl):
        d = cl.rfind(".")
        classname = cl[d + 1:len(cl)]
        m = __import__(cl[0:d], globals(), locals(), [classname])
        return getattr(m, classname)
