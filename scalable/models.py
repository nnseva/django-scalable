from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


try:
    from django.utils.translation import ugettext_lazy as _
except ImportError:
    from django.utils.translation import gettext_lazy as _


class Scalable(models.Model):
    """The base abstract class for scalable models"""

    # You may setup these values to special values for different models
    acquire_limit = None
    acquire_timeout = None

    #: When the record has started to be processed, but has not yet been completed
    acquired_at = models.DateTimeField(
        null=True, blank=True, db_index=True, editable=False,
        verbose_name=_('Acquired At'), help_text=_(
            'When the record has started to be processed, but not yet been completed, '
            'only for operational purposes'
        )
    )

    #: Who has started processing a record but has not completed it yet
    acquired_by = models.CharField(
        null=True, blank=True, db_index=True, editable=False, max_length=255,
        verbose_name=_('Acquired By'), help_text=_(
            'Who has started processing a record but not completed it yet, '
            'only for operational purposes'
        )
    )

    class Meta:
        abstract = True

    @classmethod
    def acquire(cls, acquired_by, queryset=None, acquired_at=None, limit=None):
        """
        Acquires available records for the packet processing,
        updating the corresponding fields.

        Records filtered by the queryset, or cls.objects, are acquired, no more than limit.

        If records are acquired concurrently, it is guaranteed that no more than one
        processing procedure will acquire one record.

        Acquired records may be easy got from the objects list using
        filter by the passed acquired_by parameter.

        The acquired_by should be unique per packet processing procedures
        evaluated concurrently. It is not saved after unacquiring and might be reused later.

        Returns the acquired queryset.
        """
        if queryset is None:
            queryset = cls.objects
        if not acquired_at:
            acquired_at = timezone.now()
        if not limit:
            limit = cls.acquire_limit or getattr(settings, 'SCALABLE_ACQUIRE_LIMIT', 100)

        with transaction.atomic():
            ids = queryset.filter(
                acquired_at__isnull=True,
            ).select_for_update(
                skip_locked=True
            ).values_list('pk', flat=True)[0:limit]
            ids = list(ids)
            queryset.filter(
                pk__in=ids
            ).update(
                acquired_by=acquired_by, acquired_at=acquired_at
            )

        return cls.acquired(acquired_by, queryset=queryset)

    @classmethod
    def acquired(cls, acquired_by, queryset=None):
        """Returns a queryset filtered for only records acquired by the passed ID"""
        if queryset is None:
            queryset = cls.objects
        return queryset.filter(acquired_by=acquired_by)

    @classmethod
    def unacquire(cls, acquired_by, queryset=None):
        """
        Unacquires all records acquired by the passed ID,
        cleaning up correspondent fields in an atomic transaction for the queryset.
        """
        if queryset is None:
            queryset = cls.objects
        with transaction.atomic():
            queryset.filter(
                acquired_by=acquired_by
            ).select_for_update().update(acquired_by=None, acquired_at=None)

    @classmethod
    def reacquire(cls, acquired_by, queryset=None, acquired_at=None):
        """
        Reacquires all records acquired before by the passed ID,
        renewing correspondent field in an atomic transaction for the queryset.
        """
        if not acquired_at:
            acquired_at = timezone.now()
        if queryset is None:
            queryset = cls.objects
        with transaction.atomic():
            queryset.filter(
                acquired_by=acquired_by
            ).select_for_update().update(acquired_by=acquired_by, acquired_at=acquired_at)
        return cls.acquired(acquired_by, queryset=queryset)

    @classmethod
    def unacquire_timed_out(cls, queryset=None, now=None):
        """
        Unacquires records that have been acquired too much time ago for the queryset.
        """
        if queryset is None:
            queryset = cls.objects
        if not now:
            now = timezone.now()
        with transaction.atomic():
            queryset.filter(
                acquired_at__lt=now - timezone.timedelta(
                    seconds=cls.acquire_timeout or getattr(settings, 'SCALABLE_ACQUIRE_TIMEOUT', 600)
                )
            ).select_for_update().update(acquired_by=None, acquired_at=None)
