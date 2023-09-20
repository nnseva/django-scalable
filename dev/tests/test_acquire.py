import threading
from time import sleep

from django.db import connection
from django.test import TransactionTestCase, override_settings

from .models import ScalableExample


class Test(TransactionTestCase):
    def setUp(self):
        """Prepare test env"""
        ScalableExample.acquire_limit = 3
        ScalableExample.acquire_timeout = 3

        for i in range(30):
            ScalableExample.objects.create(name='test %03d' % i)

    def test_001_simple_acquire(self):
        """Test, whether the acquire works in a simplest case"""
        a0 = ScalableExample.acquire('beginning')
        self.assertEqual(a0.count(), 3)
        for i in range(9):
            a = ScalableExample.acquire('acquire %d' % i)
            self.assertEqual(a.count(), 3)
        aq = ScalableExample.acquire('final')
        self.assertEqual(aq.count(), 0)
        for i in range(9):
            ScalableExample.unacquire('acquire %d' % i)
            self.assertEqual(ScalableExample.acquired('acquire %d' % i).count(), 0)

    def test_002_concurrent_acquire(self):
        """Test, whether the acquire works in a concurrent environment"""
        a0 = ScalableExample.acquire('beginning')
        self.assertEqual(a0.count(), 3)
        threads = []
        for i in range(9):
            def run():
                a = ScalableExample.acquire('acquire %d' % i)
                self.assertEqual(a.count(), 3)
                connection.close()
            threads.append(threading.Thread(target=run))
            threads[-1].start()
        for t in threads:
            t.join()
        aq = ScalableExample.acquire('final')
        self.assertEqual(aq.count(), 0)

    def test_003_acquire_timeout(self):
        """Test, whether the acquire timeout works"""
        a0 = ScalableExample.acquire('beginning')
        self.assertEqual(a0.count(), 3)
        ScalableExample.unacquire_timed_out()
        self.assertEqual(ScalableExample.acquired('beginning').count(), 3)
        sleep(3.1)
        ScalableExample.unacquire_timed_out()
        self.assertEqual(ScalableExample.acquired('beginning').count(), 0)

    @override_settings(
        SCALABLE_ACQUIRE_LIMIT=4
    )
    def test_004_global_acquire_limit_settings(self):
        """Test global SCALABLE_ACQUIRE_LIMIT setting"""
        ScalableExample.acquire_limit = None
        a0 = ScalableExample.acquire('beginning')
        self.assertEqual(a0.count(), 4)

    @override_settings(
        SCALABLE_ACQUIRE_TIMEOUT=4
    )
    def test_005_global_acquire_timeout_settings(self):
        """Test global SCALABLE_ACQUIRE_TIMEOUT setting"""
        ScalableExample.acquire_timeout = None
        a0 = ScalableExample.acquire('beginning')
        self.assertEqual(a0.count(), 3)
        ScalableExample.unacquire_timed_out()
        self.assertEqual(ScalableExample.acquired('beginning').count(), 3)
        sleep(3.1)
        ScalableExample.unacquire_timed_out()
        self.assertEqual(ScalableExample.acquired('beginning').count(), 3)
        sleep(1)
        ScalableExample.unacquire_timed_out()
        self.assertEqual(ScalableExample.acquired('beginning').count(), 0)

    def test_006_reacquire_timeout(self):
        """Test, whether the reacquire increaces timeout"""
        a0 = ScalableExample.acquire('beginning')
        self.assertEqual(a0.count(), 3)
        ScalableExample.unacquire_timed_out()
        self.assertEqual(ScalableExample.acquired('beginning').count(), 3)
        sleep(2)
        ScalableExample.reacquire('beginning')
        sleep(2)
        ScalableExample.unacquire_timed_out()
        self.assertEqual(ScalableExample.acquired('beginning').count(), 3)
        sleep(2)
        ScalableExample.unacquire_timed_out()
        self.assertEqual(ScalableExample.acquired('beginning').count(), 0)
