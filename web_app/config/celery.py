import logging
import os

from celery import Celery
from celery.app.task import Task
from celery.signals import before_task_publish, setup_logging
from celery.utils import abstract

from apps.core.app_context import app_context

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

logger = logging.getLogger(__name__)

celery_app = Celery("inHome")
celery_app.config_from_object("django.conf:settings", namespace="CELERY")


@abstract.CallableTask.register
class AppContextAwareTask(Task):  # noqa
    def __call__(self, *args, **kwargs):
        from apps.core.auth import User

        trace_id = kwargs.pop("app_context_trace_id", None)
        app_context.set(trace_id=trace_id)

        if user_id := kwargs.pop("app_context_user_id", None):
            user = User.objects.get(id=user_id)  # to provide User object in context
            app_context.set(user=user, user_id=user_id)

        logger.info(
            "Starting task %s[%s]: args=%s, kwargs=%s",
            self.__class__.name,
            self.request.id,
            self.request.args,
            self.request.kwargs,
        )

        result = Task.__call__(self, *args, **kwargs)

        logger.info(
            "Completed task %s[%s]: args=%s, kwargs=%s, result=%s",
            self.__class__.name,
            self.request.id,
            self.request.args,
            self.request.kwargs,
            result,
        )
        return result


@before_task_publish.connect
def task_publish_handler(sender=None, headers=None, body=None, **kwargs):  # noqa
    """
    Method to add extra parameters to task call right after .delay() or .apply_async() completes.
    We can't patch apply_async() method directly because it has validations after that.
    """
    task_args, task_kwargs, task_options = body
    # NOTE: here we modify task_kwargs in-place by reference to a body variable
    task_kwargs["app_context_trace_id"] = app_context.trace_id
    task_kwargs["app_context_user_id"] = app_context.user.id if app_context.user else None
    logger.info(
        "Scheduled task %s[%s]: args=%s, kwargs=%s",
        headers["task"],
        headers["id"],
        task_args,
        task_kwargs,
    )


@setup_logging.connect
def setup_celery_logging(**kwargs):  # noqa
    """Otherwise Celery ignores Django LOGGING settings."""
    import logging.config

    from django.conf import settings

    logging.config.dictConfig(settings.LOGGING)


# Replace default Task class with our custom one
celery_app.Task = AppContextAwareTask  # noqa

celery_app.autodiscover_tasks()
