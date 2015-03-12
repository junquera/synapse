# -*- coding: utf-8 -*-
# Copyright 2015 OpenMarket Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Because otherwise 'resource' collides with synapse.metrics.resource
from __future__ import absolute_import

import logging
from resource import getrusage, getpagesize, RUSAGE_SELF

from .metric import (
    CounterMetric, CallbackMetric, DistributionMetric, CacheMetric
)


logger = logging.getLogger(__name__)


# We'll keep all the available metrics in a single toplevel dict, one shared
# for the entire process. We don't currently support per-HomeServer instances
# of metrics, because in practice any one python VM will host only one
# HomeServer anyway. This makes a lot of implementation neater
all_metrics = {}


class Metrics(object):
    """ A single Metrics object gives a (mutable) slice view of the all_metrics
    dict, allowing callers to easily register new metrics that are namespaced
    nicely."""

    def __init__(self, name):
        self.name_prefix = name

    def _register(self, metric_class, name, *args, **kwargs):
        full_name = "%s_%s" % (self.name_prefix, name)

        metric = metric_class(full_name, *args, **kwargs)

        all_metrics[full_name] = metric
        return metric

    def register_counter(self, *args, **kwargs):
        return self._register(CounterMetric, *args, **kwargs)

    def register_callback(self, *args, **kwargs):
        return self._register(CallbackMetric, *args, **kwargs)

    def register_distribution(self, *args, **kwargs):
        return self._register(DistributionMetric, *args, **kwargs)

    def register_cache(self, *args, **kwargs):
        return self._register(CacheMetric, *args, **kwargs)


def get_metrics_for(pkg_name):
    """ Returns a Metrics instance for conveniently creating metrics
    namespaced with the given name prefix. """

    # Convert a "package.name" to "package_name" because Prometheus doesn't
    # let us use . in metric names
    return Metrics(pkg_name.replace(".", "_"))


def render_all():
    strs = []

    # TODO(paul): Internal hack
    update_resource_metrics()

    for name in sorted(all_metrics.keys()):
        try:
            strs += all_metrics[name].render()
        except Exception as e:
            strs += ["# FAILED to render %s" % name]
            logger.exception("Failed to render %s metric", name)

    strs.append("")  # to generate a final CRLF

    return "\n".join(strs)


# Now register some standard process-wide state metrics, to give indications of
# process resource usage

rusage = None
PAGE_SIZE = getpagesize()


def update_resource_metrics():
    global rusage
    rusage = getrusage(RUSAGE_SELF)

resource_metrics = get_metrics_for("process.resource")

# msecs
resource_metrics.register_callback("utime", lambda: rusage.ru_utime * 1000)
resource_metrics.register_callback("stime", lambda: rusage.ru_stime * 1000)

# pages
resource_metrics.register_callback("maxrss", lambda: rusage.ru_maxrss * PAGE_SIZE)
