import numpy
import pytest

from thinc.api import Optimizer, registry
from thinc.optimizers import KeyT, _wrap_generator

STUB_KEY: KeyT = (0, "")


def _test_schedule_valid():
    while True:
        yield 0.456


def _test_schedule_invalid():
    yield from []


@pytest.fixture(
    params=[
        (lambda: 0.123, 0.123, 0.123, 0.123),
        (lambda: _test_schedule_valid(), 0.456, 0.456, 0.456),
        (lambda: (i for i in [0.2, 0.1, 0.4, 0.5, 0.6, 0.7, 0.8]), 0.2, 0.1, 0.4),
        (lambda: (i for i in [0.333, 0.666]), 0.333, 0.666, 0.666),
        (lambda: [0.9, 0.8, 0.7], 0.9, 0.8, 0.7),
        (lambda: [0.0, 0.123], 0.0, 0.123, 0.123),
    ],
    scope="function",
)
def schedule_valid(request):
    # Use lambda to prevent iterator from being consumed by first test
    r_func, r1, r2, r3 = request.param
    return r_func(), r1, r2, r3


@pytest.fixture(
    params=[
        (lambda: 0.123, 0.123, 0.123, 0.123),
        (lambda: (i for i in [0.2, 0.1, 0.4, 0.5, 0.6, 0.7, 0.8]), 0.2, 0.1, 0.4),
        (lambda: (i for i in [0.333, 0.666]), 0.333, 0.666, 0.666),
        (lambda: [0.9, 0.8, 0.7], 0.9, 0.8, 0.7),
        (lambda: [0.0, 0.123], 0.0, 0.123, 0.123),
    ],
    scope="function",
)
def schedule_config_valid(request):
    # Use lambda to prevent iterator from being consumed by first test
    r_func, r1, r2, r3 = request.param
    return r_func(), r1, r2, r3


@pytest.fixture(
    params=[
        (lambda: "hello"),
        (lambda: _test_schedule_invalid()),
        (lambda: (_ for _ in [])),
        (lambda: []),
    ],
    scope="function",
)
def schedule_invalid(request):
    # Use lambda to prevent iterator from being consumed by first test
    r_func = request.param
    return r_func()


@pytest.mark.parametrize("name", ["RAdam.v1", "Adam.v1", "SGD.v1"])
def test_optimizers_from_config(name):
    learn_rate = 0.123
    cfg = {"@optimizers": name, "learn_rate": learn_rate}
    optimizer = registry.resolve({"config": cfg})["config"]
    assert optimizer.learn_rate(step=optimizer._step, key=STUB_KEY) == learn_rate


def test_optimizer_schedules_from_config(schedule_config_valid):
    lr, lr_next1, lr_next2, lr_next3 = schedule_config_valid
    cfg = {"@optimizers": "Adam.v1", "learn_rate": lr}
    optimizer = registry.resolve({"cfg": cfg})["cfg"]
    assert optimizer.learn_rate(step=optimizer._step, key=STUB_KEY) == lr_next1
    optimizer.step_schedules()
    assert optimizer.learn_rate(step=optimizer._step, key=STUB_KEY) == lr_next2
    optimizer.step_schedules()
    assert optimizer.learn_rate(step=optimizer._step, key=STUB_KEY) == lr_next3
    optimizer.learn_rate = lambda *, step, key: 1.0
    assert optimizer.learn_rate(step=optimizer._step, key=STUB_KEY) == 1.0


def test_optimizer_schedules_valid(schedule_valid):
    lr, lr_next1, lr_next2, lr_next3 = schedule_valid
    optimizer = Optimizer(learn_rate=lr)
    assert optimizer.learn_rate(step=optimizer._step, key=STUB_KEY) == lr_next1
    optimizer.step_schedules()
    assert optimizer.learn_rate(step=optimizer._step, key=STUB_KEY) == lr_next2
    optimizer.step_schedules()
    assert optimizer.learn_rate(step=optimizer._step, key=STUB_KEY) == lr_next3
    optimizer.learn_rate = lambda *, step, key: 1.0
    assert optimizer.learn_rate(step=optimizer._step, key=STUB_KEY) == 1.0


def test_optimizer_schedules_invalid(schedule_invalid):
    with pytest.raises(ValueError):
        Optimizer(learn_rate=schedule_invalid)


def test_optimizer_init():
    optimizer = Optimizer(
        learn_rate=0.123,
        use_averages=False,
        use_radam=True,
        L2=0.1,
        L2_is_weight_decay=False,
    )
    _, gradient = optimizer((0, "x"), numpy.zeros((1, 2)), numpy.zeros(0))
    assert numpy.array_equal(gradient, numpy.zeros(0))
    W = numpy.asarray([1.0, 0.0, 0.0, 1.0], dtype="f").reshape((4,))
    dW = numpy.asarray([[-1.0, 0.0, 0.0, 1.0]], dtype="f").reshape((4,))
    optimizer((0, "x"), W, dW)
    optimizer = Optimizer(learn_rate=0.123, beta1=0.1, beta2=0.1)
    optimizer((1, "x"), W, dW)


def test_optimizer_last_score():
    optimizer = Optimizer(
        learn_rate=0.123,
    )

    assert optimizer.last_score is None
    optimizer.last_score = 1.0
    assert optimizer.last_score == (0, 1.0)
    optimizer.step_schedules()
    optimizer.step_schedules()
    assert optimizer.last_score == (0, 1.0)
    optimizer.last_score = 2.0
    assert optimizer.last_score == (2, 2.0)


def test_generator_schedule():
    s = _wrap_generator("test", iter([0.0, 1.0, 2.0, 3.0]))
    assert s(step=0, key=STUB_KEY, last_score=None) == 0.0
    assert s(step=0, key=STUB_KEY, last_score=None) == 0.0
    assert s(step=1, key=STUB_KEY, last_score=None) == 1.0
    assert s(step=1, key=STUB_KEY, last_score=None) == 1.0
    assert s(step=3, key=STUB_KEY, last_score=None) == 3.0
    assert s(step=10, key=STUB_KEY, last_score=None) == 3.0

    with pytest.raises(ValueError, match=r"must not decrease"):
        s(step=1, key=STUB_KEY, last_score=None)
