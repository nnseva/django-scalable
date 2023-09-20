# Django-Scalable

The Django-Scalable package introduces a base abstract Scalable class,
inherited from the Model class, and some number of utilities, appropriate
to spread processing a huge set of instances to any number of workers
running in parallel.

## Installation

*Stable version* from the PyPi package repository
```bash
pip install django-scalable
```

*Last development version* from the GitHub source version control system
```
pip install git+git://github.com/nnseva/django-scalable.git
```

## Compatibility

The package uses `select_for_update()` call with `skip_locked` parameter,
so it is compatible with the only restricted set of database backends:

- PostgreSQL
- Oracle
- MySQL 8.0.1+
- MariaDB 10.6+

See details in the [Django documentation](https://docs.djangoproject.com/en/dev/ref/models/querysets/#select-for-update).

## Configuration

Include the `scalable` application into the `INSTALLED_APPS` list, like:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    ...
    'scalable',
    ...
]
```
Use the following available settings to tune the package behaviour:

- `SCALABLE_ACQUIRE_TIMEOUT` - the maximum single processing timeout in seconds, after which
the acquired instance should be unaquired automatically, and processing will be tried to start
again. Default is `600`.

- `SCALABLE_ACQUIRE_LIMIT` - the maximum number of instances to be aquired simultaneously
by one call of `aquire`. Default is `100`.

# Introduction

## Inspiration

Let's imaging that you have a huge table with a lot of instances to be processed
by some algorithm.

The algorithm processes every instance separately, and independently, so you can
parallelize processing to some number of workers, which could process these instances.
But how to spread instances among your workers, to avoid:

- double processing, when two workers try to aquire the same instance to process simultaneously
- single worker overload, when too many instances to be processed appear unexpectedly and aquired by one worker

The package solves these problems.

## Acquire-process-unacquire

The whole processing of one instance may be introduced as the following sequence of three steps:

- acquire an instance by the single worker, so other workers will not try to acquire it
- process the instance, evaluating an algorithm on the acquired instance
- unacquire (free) the instance

We will acquire an instance (really some number of instances, determined by the `SCALABLE_ACQUIRE_LIMIT` setting)
updating special fields, and allow selecting acquired instances for processing by the worker. The
package provides methods to acquire and unacquire instances, select instances acquired by this worker, and
unaquire instances whose processing took too much time.

The timeout proceed may mean, that the processing was stopped unexpectedly because of worker crash, and
needs to be restarted again. Select the timeout length to the appropriate value. While too long
processing is running, a special reacquire method may be called to renew the acquire timestamp
and avoid unacquiring of instances processed properly, but too much time.

# Using

You should inherit your model from `scalable.Scalable` abstract model to make it using the package.
This base model introduces two additional fields to the model:

- acquired_by
- acquired_at

Fields are indexed, and filled by non-null value only when the instance is acquired. They are marked as
`editable=False`, so will not be visible from the admin, or API by default. However, you can make them visible
using explicit declaration of readonly fields in admin or API.

Use model-wide methods to manipulate instances on the low level, as described in the chapter below.

## Low-level acquire

The low-level model-wide methods allow directly:

- `acquire()` - acquire a set of instances
- `reacquire()` - reacquire this set while too long processing time
- `acquired()` - get this set of instances as a queryset
- `unacquire()` - unacquire the set of instances acquired before
- `unacquire_timed_out()` - cleanup acquire fields of instances acquired at too much time ago

All these methods are model-wide, so you should use a class method call syntax to call them.

For example, if your model is called `Person`, you will use the following symtax to call `acquire()`:

```python
    acquired = Person.acquire(worker_name)
```

### Scalable attributes

- `acquire_limit` determines maximum number of model instances acquired by one `acquire` call
- `acquire_timeout` determines a maximum time limit while acquired instances remain acquired without `reacquire` call

While attributes have a None value, the global settings are used instead:

- `settings.SCALABLE_ACQUIRE_LIMIT` for `acquire_limit`
- `settings.SCALABLE_ACQUIRE_TIMEOUT` for `acquire_timeout`

If no global settings are set, the following defaults are used:

- `100` for `settings.SCALABLE_ACQUIRE_LIMIT`
- `600` for `settings.SCALABLE_ACQUIRE_TIMEOUT`

### Scalable fields

The scalable fields are inherited by all models inherited from the `Scalable`:

- `acquired_at` - timestamp of acquire/reacquire action
- `acquired_by` - string value of the `acquired_by` parameter of the `acquire` function call

Instances have a non-null value in these fields only while the instance is acquired.

### Scalable.acquire(acquired_by, queryset=None, acquired_at=None, limit=None)

Acquires a set of model instances. A size of the set is limited by the `limit` parameter, which by default may be
determined by the global `SCALABLE_ACQUIRE_LIMIT` setting, or `acquire_limit` class-wide variable member.
If no any of these variables are set, value `100` is used as a default.

The `acquired_by` string parameter identifies worker which acquires instances.
Use any unique among concurrent workers name. When these instances are unacquired, the name appears
to be free and available to reuse. You can use same names in models having different tables in the database.
All just acquired instances will have the same value in the `acquired_by` field,
equal to the `acquired_by` parameter of the `acquire()` method call.

The `acquired_at` parameter may be used to manually set the `acquired_at` field of the acquired instance.
The default value is got calling `timezone.now()`. This field plays the role only when `unacquire_timed_out()`
is called.

You can use `queryset` parameter to make the source queryset differ from the `objects` member of the model.

Use `queryset` if you would not like to acquire any available instances, but rather should acquire only filtered
subset of the model instances.

For example, if your model is called `Person`, you can use the following symtax to call `acquire()` to acquire
only male persons:

```python
    acquired = Person.acquire(worker_name, queryset=Person.objects.filter(gender='male'))
```

The returned queryset is based on the `acquired_by` worker name filter, having a nature of something like a snapshot.
The future scan of the `acquired` instances will return the same list of instances, until unacquired, even when they
change values of fields used to make a filter of the original queryset.

### Scalable.unacquire(acquired_by, queryset=None)

Unacquires a set of model instances identified by the `acquired_by` worker name. It unacquires all identified
instances by default, but can be restricted by the `queryset` explicitly passed as a parameter. Unacquire just
updates fields `acquired_by` and `acquired_at` of filtered instances to the null values.

### Scalable.reacquire(acquired_by, queryset=None, acquired_at=None)

Reacquires a set of model instances, just updating the `acquired_by` to the passed value, or to the
`timezone.now()` value by default.

Present parameters and return value have same meaning as for the `acquire()` call.

### Scalable.acquired(acquired_by, queryset=None)

Returns a queryset containing a current list of acquired instances. You can restrict this
queryset passing a `queryset` patrameter. It will be used instead of the `objects` member of the model
to create a queryset to be returned.

### Scalable.unacquire_timed_out(queryset=None, now=None)

Unacquires all instances whose `acquired_at` field has a value lower than `now` minus acquire timeout.
The `now` parameter will have a value `timezone.now()` by default.

The `queryset` parameter may be used to filter out instances. The `objects` model attribute will be
used by default, if `queryset` parameter is not passed.

## TODO:

- auto-reacquire while acquired, in a separate thread
- async versions of low-level methods for Django>=4.2
- high-level `scalable` contextmanager/decorator, sync and async (async for Django>=4.2)
