import numpy
import pytest
from numpy.testing import assert_allclose

from ...ops import Ops
from ...vec2vec import Affine
from ...exceptions import ShapeError


class MockOps(Ops):
    def __init__(self):
        pass

    def allocate(self, shape, name=None):
        return numpy.zeros(shape)

    def allocate_pool(self, nr_weight, name=None):
        return DataPool(nr_weight)

    def affine(self, W_oi, b_o, input_bi):
        return numpy.ones((input_bi.shape[0], W_oi.shape[0]))

    def get_dropout(self, shape, drop):
        if drop <= 0:
            return None
        else:
            return numpy.ones(shape) * (1-drop)
    
    def batch_dot(self, x, y):
        return numpy.tensordot(x, y, axes=[[1], [1]])

    def batch_outer(self, x, y):
        return numpy.tensordot(x, y, axes=[[0], [0]])

    def xavier_uniform_init(self, W, inplace=True):
        pass


class DataPool(object):
    def __init__(self, nr_weight):
        self.data = numpy.zeros((nr_weight,))
        self.i = 0

    def allocate(self, nr_weight):
        data = self.data[self.i : self.i + nr_weight]
        self.i += nr_weight
        return data


@pytest.fixture
def ops():
    return MockOps()


@pytest.fixture
def model(ops):
    return Affine(ops=ops, nr_out=10, nr_in=6)


def test_init(ops):
    model = Affine(ops=ops, nr_out=10, nr_in=6)
    assert model.nr_out == 10
    assert model.nr_in == 6
    assert model.W is None
    assert model.b is None
    assert isinstance(model.ops, MockOps)


def test_nr_weight(model):
    assert model.nr_weight == (model.nr_out * model.nr_in) + model.nr_out


def test_initialize_weights_no_pool(model):
    input_ = model.ops.allocate((5, 6))
    model.initialize_weights(input_)
    assert model.W.shape == (model.nr_out, model.nr_in)
    assert model.b.shape == (model.nr_out,)


def test_initialize_weights_pool(model):
    pool = DataPool(model.nr_weight)
    input_ = model.ops.allocate((5, 6))
    model.initialize_weights(input_, data=pool)
    assert model.W.shape == (model.nr_out, model.nr_in)
    assert model.b.shape == (model.nr_out,)


def test_predict_batch_bias(model):
    input_ = model.ops.allocate((5, 6))
    model.initialize_weights(input_)
    model.b.fill(1)
    output = model.predict_batch(input_)
    assert output.shape == (5, 10)


def test_predict_batch_weights(model):
    input_ = model.ops.allocate((5, 6))
    model.initialize_weights(input_)
    output = model.predict_batch(input_)
    assert output.shape == (5, 10)
    assert all([val == 1. for val in output.flatten()]), output


def test_begin_update(model):
    input_ = model.ops.allocate((5, 6))
    model.initialize_weights()
    output, finish_update = model.begin_update(input_)
    assert output.shape == (5, 10)
    assert all([val == 1. for val in output.flatten()]), output


def test_finish_update(model):
    def sgd(data, gradient):
        assert data.shape == gradient.shape

    input_ = model.ops.allocate((5, 6))
    model.initialize_weights(input_)
    output, finish_update = model.begin_update(input_)
    gradient = model.ops.allocate(output.shape)
    d_input = finish_update(gradient, sgd)
    assert d_input.shape == input_.shape


def test_predict_batch_not_batch(model):
    model.initialize_weights()
    input_ = model.ops.allocate((6,))
    with pytest.raises(ShapeError):
        model.begin_update(input_)


def test_predict_update_dim_mismatch(model):
    model.initialize_weights()
    input_ = model.ops.allocate((10, 5))
    with pytest.raises(ShapeError):
        model.begin_update(input_)


def test_begin_update_not_batch(model):
    model.initialize_weights()
    input_ = model.ops.allocate((6,))
    with pytest.raises(ShapeError):
        model.begin_update(input_)


def test_begin_update_dim_mismatch(model):
    model.initialize_weights()
    input_ = model.ops.allocate((10, 5))
    with pytest.raises(ShapeError):
        model.begin_update(input_)