from django.db import models

from scalable.models import Scalable


try:
    from django.utils.translation import ugettext_lazy as _
except ImportError:
    from django.utils.translation import gettext_lazy as _


class ScalableExample(Scalable):
    """ Scalable Example """
    name = models.CharField(
        max_length=128, unique=True,
        verbose_name=_('Name'),
        help_text=_('Name of the record to be shown to the user')
    )

    processing_timer = models.IntegerField(
        null=True, blank=True,
        verbose_name=_('Processing Timer'),
        help_text=_('Processing timer increments every second while processing')
    )

    def __str__(self):
        return _('%s: %s') % (self.name, self.processing_timer or 'idle')

    class Meta:
        verbose_name = _('Scalable Example')
        verbose_name_plural = _('Scalable Examples')
