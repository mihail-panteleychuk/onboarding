import logging
import os
import re
from typing import Dict

from django.conf import settings
from prometheus_client import CollectorRegistry, Counter, Summary, generate_latest, push_to_gateway
from prometheus_client.exposition import basic_auth_handler, default_handler  # noqa

logger = logging.getLogger(__name__)


# Enables/disables push on shutdown, but other methods "silently" work.
PROMETHEUS_ENABLED = os.environ.get("PROMETHEUS_ENABLED", default="false").lower() in ("true", "1")

PROMETHEUS_ENVIRONMENT = os.environ.get("PROMETHEUS_ENVIRONMENT", default="local")
PROMETHEUS_USERNAME = os.environ.get("PROMETHEUS_USERNAME", default=None)
PROMETHEUS_PASSWORD = os.environ.get("PROMETHEUS_PASSWORD", default=None)

PROMETHEUS_METRIC_NAMESPACE = os.environ.get(
    "PROMETHEUS_METRIC_NAMESPACE",
    default="in_home_project_back",
)

# To push metrics to Prometheus PushGateway
# PROMETHEUS_PUSHGATEWAY = os.environ.get("PROMETHEUS_PUSHGATEWAY", default="pushgateway:9091")
# PROMETHEUS_PUSH_JOB_NAME = os.environ.get("PROMETHEUS_PUSH_JOB_NAME", default="in_home_project_back")

# To push metrics right after tracking
PROMETHEUS_PUSH_IMMEDIATELY = os.environ.get(
    "PROMETHEUS_PUSH_IMMEDIATELY",
    default="False",
).lower() in ("true", "1")

GENERAL_LABEL_NAMES = [
    "project_name",
    "environment",
]
GENERAL_LABELS = {
    "project_name": PROMETHEUS_METRIC_NAMESPACE,
    "environment": PROMETHEUS_ENVIRONMENT,
}


class PrometheusClient:
    """
    Counter - go up, and reset when the process restarts;
        x = Counter('my_failures', 'Description of counter')
        x.inc()
    Gauges - like Counters, but can go up and down;
        x = Gauge('my_inprogress_requests', 'Description of gauge')
        x.inc()
        x.dec(10)
        x.set(4.2
    Summaries - track the value at certain moment (e.g. size and number of events);
        x = Summary('request_latency_seconds', 'Description of summary')
        x.observe(4.7)
    Histograms - like Summaries but with buckets, which allows for aggregatable calculation of quantiles;
        x = Histogram('request_latency_seconds', 'Description of histogram')
        x.observe(4.7)
    Info - tracks key-value information, usually about a whole target;
        x = Info('my_build_version', 'Description of info')
        x.info({'version': '1.2.3', 'buildhost': 'foo@bar'})
    Enum - tracks which of a set of states something is currently in.
        x = Enum('my_task_state', 'Description of enum', states=['starting', 'running', 'stopped'])
        x.state('running')
    """

    trackers = {}
    registry = CollectorRegistry()

    def __init__(
        self,
        namespace: str = "",
        push_gateway_host: str = "",
        job_name: str = "",
        username: str = None,
        password: str = None,
        force_push_immediately: bool = False,
        enabled: bool = True,
    ):
        self.namespace = namespace
        self.push_gateway_host = push_gateway_host
        self.job_name = job_name
        self._username = username
        self._password = password
        self.force_push_immediately = force_push_immediately
        self.enabled = enabled

    def _registry_auth_handler(self, url, method, timeout, headers, data):
        if self._username and self._password:
            return basic_auth_handler(
                url,
                method,
                timeout,
                headers,
                data,
                self._username,
                self._password,
            )
        else:
            return default_handler(url, method, timeout, headers, data)

    def push_to_gateway(self):
        if not self.enabled or not self.push_gateway_host:
            logger.debug("Prometheus not enabled, skipping push to gateway")
            return

        if not settings.IS_LOCAL:
            logger.debug("Prometheus not enabled in local development, skipping push to gateway")
            return

        try:
            logger.info("Starting push Prometheus metrics to Gateway")
            push_to_gateway(
                gateway=self.push_gateway_host,
                job=self.job_name,
                registry=self.registry,
                handler=self._registry_auth_handler,
            )
            logger.info("Successfully pushed Prometheus metrics to Gateway")
        except Exception as e:
            logger.exception("Failed to push Prometheus metrics to Gateway: %s", e)
            # TODO: should we print them to logs?

    def generate_latest(self, registry=None):
        logger.debug("Prometheus asked for latest metrics")
        return generate_latest(registry=registry or self.registry)

    @staticmethod
    def validate_metric_name(name: str):
        """
        Specify the general feature of a system that is measured
        (e.g. http_requests_total - the total number of HTTP requests received).
        Metric names may contain ASCII letters, digits, underscores, and colons.
        It must match the regex `[a-zA-Z_:][a-zA-Z0-9_:]*`.

        Source: https://prometheus.io/docs/concepts/data_model/#metric-names-and-labels
        """
        is_valid = re.match(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$", name)
        return bool(is_valid)

    @staticmethod
    def validate_metric_label(name: str):
        """
        Enable Prometheus's dimensional data model to identify any given combination of labels for the same metric name.
        It identifies a particular dimensional instantiation of that metric
        (for example: all HTTP requests that used the method POST to the /api/tracks handler).
        The query language allows filtering and aggregation based on these dimensions.
        The change of any label's value, including adding or removing labels, will create a new time series.
        Labels may contain ASCII letters, numbers, as well as underscores. They must match the regex `[a-zA-Z_][a-zA-Z0-9_]*`.
        Label names beginning with __ (two "_") are reserved for internal use.
        Label values may contain any Unicode characters.
        Labels with an empty label value are considered equivalent to labels that do not exist.

        Source: https://prometheus.io/docs/concepts/data_model/#metric-names-and-labels
        """
        is_valid = re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name)
        return bool(is_valid)

    def _get_tracker(
        self,
        tracker_class,
        tracker_name: str,
        description: str,
        label_names: list = (),
        labels: dict = None,
    ):
        if tracker_name not in self.trackers:
            self.validate_metric_name(tracker_name)
            _labels = GENERAL_LABELS.copy()
            if labels:
                map(self.validate_metric_label, labels)  # validates all labels
                _labels.update(labels)

            self.trackers[tracker_name] = tracker_class(
                name=f"{PROMETHEUS_METRIC_NAMESPACE}_{tracker_name}",
                documentation=description,
                labelnames=GENERAL_LABEL_NAMES + list(label_names),
                registry=self.registry,
            ).labels(**_labels)
        return self.trackers[tracker_name]

    # -------------------

    def metric_inc(
        self,
        tracker_name: str,
        description: str,
        label_names: list = (),
        labels: dict = None,
        amount: [int, float] = 1,
        exemplar: Dict[str, str] = None,
    ):
        try:
            tracker = self._get_tracker(Counter, tracker_name, description, label_names, labels)
            tracker.inc(amount=amount, exemplar=exemplar)
            if self.force_push_immediately:
                self.push_to_gateway()
        except Exception as e:
            logger.exception("Failed to track metric to Prometheus: %s", e)

    def metric_duration(
        self,
        tracker_name: str,
        description: str,
        label_names: list = (),
        labels: dict = None,
        duration: [int, float] = 1,
        exemplar: Dict[str, str] = None,
    ):
        try:
            tracker = self._get_tracker(Counter, tracker_name, description, label_names, labels)
            tracker.observe(amount=duration, exemplar=exemplar)
            if self.force_push_immediately:
                self.push_to_gateway()
        except Exception as e:
            logger.exception("Failed to track metric to Prometheus: %s", e)

    def metric_level(
        self,
        tracker_name: str,
        description: str,
        label_names: list = (),
        labels: dict = None,
        level: [int, float] = 1,
    ):
        try:
            tracker = self._get_tracker(Summary, tracker_name, description, label_names, labels)
            tracker.set(level)
            if self.force_push_immediately:
                self.push_to_gateway()
        except Exception as e:
            logger.exception("Failed to track metric to Prometheus: %s", e)


prometheus_client = PrometheusClient(
    enabled=PROMETHEUS_ENABLED,
    namespace=PROMETHEUS_METRIC_NAMESPACE,
    username=PROMETHEUS_USERNAME,
    password=PROMETHEUS_PASSWORD,
    force_push_immediately=PROMETHEUS_PUSH_IMMEDIATELY,
    # push_gateway_host=PROMETHEUS_PUSHGATEWAY,
    # job_name=PROMETHEUS_PUSH_JOB_NAME,
)


def main():
    import datetime

    prometheus_client.metric_inc(
        tracker_name="test_metric",
        description="Metric to track successful runs",
        label_names=["name"],
        labels={"name": "test_run"},
        exemplar={"timestamp": datetime.datetime.utcnow().isoformat()},
    )
    prometheus_client.push_to_gateway()


if __name__ == "__main__":
    main()
