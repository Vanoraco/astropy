# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""
Tests for model evaluation.
Compare the results of some models with other programs.
"""
from __future__ import division
from .. import models
from ..core import (LabeledInput, SerialCompositeModel, ParallelCompositeModel,
                    Parametric1DModel, Parametric2DModel)
from ..polynomial import PolynomialModel
import numpy as np
from numpy.testing import utils
from ...tests.helper import pytest
from .. import fitting
from .example_models import models_1D, models_2D

try:
    from scipy import optimize
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


class TestSerialComposite(object):

    """
    Test composite models evaluation in series
    """
    def setup_class(self):
        self.x, self.y = np.mgrid[:5, :5]
        self.p1 = models.Polynomial1DModel(3)
        self.p11 = models.Polynomial1DModel(3)
        self.p2 = models.Polynomial2DModel(3)

    def test_single_array_input(self):
        model = SerialCompositeModel([self.p1, self.p11])
        result = model(self.x)
        xx = self.p11(self.p1(self.x))
        utils.assert_almost_equal(xx, result)

    def test_labeledinput_1(self):
        labeled_input = LabeledInput([self.x, self.y], ['x', 'y'])
        model = SerialCompositeModel([self.p2, self.p1],
                                     [['x', 'y'], ['z']],
                                     [['z'], ['z']])
        result = model(labeled_input)
        z = self.p2(self.x, self.y)
        z1 = self.p1(z)
        utils.assert_almost_equal(z1, result.z)

    def test_labeledinput_2(self):
        labeled_input = LabeledInput([self.x, self.y], ['x', 'y'])
        rot = models.MatrixRotation2D(angle=23.4)
        offx = models.ShiftModel(-2)
        offy = models.ShiftModel(1.2)
        model = SerialCompositeModel([rot, offx, offy],
                                     [['x', 'y'], ['x'], ['y']],
                                     [['x', 'y'], ['x'], ['y']])
        result = model(labeled_input)
        x, y = rot(self.x, self.y)
        x = offx(x)
        y = offy(y)
        utils.assert_almost_equal(x, result.x)
        utils.assert_almost_equal(y, result.y)

    def test_labeledinput_3(self):
        labeled_input = LabeledInput([2, 4.5], ['x', 'y'])
        rot = models.MatrixRotation2D(angle=23.4)
        offx = models.ShiftModel(-2)
        offy = models.ShiftModel(1.2)
        model = SerialCompositeModel([rot, offx, offy],
                                     [['x', 'y'], ['x'], ['y']],
                                     [['x', 'y'], ['x'], ['y']])
        result = model(labeled_input)
        x, y = rot(2, 4.5)
        x = offx(x)
        y = offy(y)
        utils.assert_almost_equal(x, result.x)
        utils.assert_almost_equal(y, result.y)

    def test_multiple_input(self):
        rot = models.MatrixRotation2D(angle=-60)
        model = SerialCompositeModel([rot, rot])
        xx, yy = model(self.x, self.y)
        inverse_model = model.inverse()
        x1, y1 = inverse_model(xx, yy)
        utils.assert_almost_equal(x1, self.x)
        utils.assert_almost_equal(y1, self.y)


class TestParallelComposite(object):

    """
    Test composite models evaluation in parallel
    """
    def setup_class(self):
        self.x, self.y = np.mgrid[:5, :5]
        self.p1 = models.Polynomial1DModel(3)
        self.p11 = models.Polynomial1DModel(3)
        self.p2 = models.Polynomial2DModel(3)

    def test_single_array_input(self):
        model = ParallelCompositeModel([self.p1, self.p11])
        result = model(self.x)
        delta11 = self.p11(self.x)
        delta1 = self.p1(self.x)
        xx = self.x + delta1 + delta11
        utils.assert_almost_equal(xx, result)

    def test_labeledinput(self):
        labeled_input = LabeledInput([self.x, self.y], ['x', 'y'])
        model = ParallelCompositeModel([self.p1, self.p11], inmap=['x'], outmap=['x'])
        result = model(labeled_input)
        delta11 = self.p11(self.x)
        delta1 = self.p1(self.x)
        xx = self.x + delta1 + delta11
        utils.assert_almost_equal(xx, result.x)

    def test_inputs_outputs_mismatch(self):
        p2 = models.Polynomial2DModel(1)
        ch2 = models.Chebyshev2DModel(1, 1)
        with pytest.raises(AssertionError):
            ParallelCompositeModel([p2, ch2])


def test_pickle():
    import copy_reg
    import types
    import cPickle

    def reduce_method(m):
        return (getattr, (m.__self__, m.__func__.__name__))

    copy_reg.pickle(types.MethodType, reduce_method)

    p1 = models.Polynomial1DModel(3)
    p11 = models.Polynomial1DModel(4)
    g1 = models.Gaussian1DModel(10.3, 5.4, 1.2)
    serial_composite_model = SerialCompositeModel([p1, g1])
    parallel_composite_model = ParallelCompositeModel([serial_composite_model, p11])
    s = cPickle.dumps(parallel_composite_model)
    s1 = cPickle.loads(s)
    assert s1(3) == parallel_composite_model(3)


@pytest.mark.skipif('not HAS_SCIPY')
def test_custom_model(amplitude=4, frequency=1):
    @models.custom_model_1d
    def SineModel(x, amplitude=4, frequency=1):
        """
        Model function
        """
        return amplitude * np.sin(2 * np.pi * frequency * x)
    x = np.linspace(0, 4, 50)
    sin_model = SineModel()
    np.random.seed(0)
    data = sin_model(x) + np.random.rand(len(x)) - 0.5
    fitter = fitting.NonLinearLSQFitter(sin_model)
    fitter(x, data)
    assert np.all((fitter.fitparams - np.array([amplitude, frequency])) < 0.001)


class TestParametricModels(object):
    """
    Test class for all parametric models.

    Test values have to be defined in example_models.py. It currently test the model
    with different input types, evaluates the model at different positions and
    assures that it gives the correct values. And tests if the  model works with
    the NonLinearFitter.
    """

    def setup_class(self):
        self.N = 100
        self.M = 100
        self.eval_error = 0.0001
        self.fit_error = 0.1
        self.x = 5.3
        self.y = 6.7
        self.x1 = np.arange(1, 10, .1)
        self.y1 = np.arange(1, 10, .1)
        self.x2, self.y2 = np.mgrid[:10, :8]

    @pytest.mark.parametrize(('model_class'), models_1D.keys())
    def test_input1D(self, model_class):
        """
        Test model with different input types.
        """
        parameters = models_1D[model_class]['parameters']
        model = create_model(model_class, parameters)
        model(self.x)
        model(self.x1)
        model(self.x2)

    @pytest.mark.parametrize(('model_class'), models_1D.keys())
    def test_eval1D(self, model_class):
        """
        Test model values at certain given points
        """
        parameters = models_1D[model_class]['parameters']
        model = create_model(model_class, parameters)
        x = models_1D[model_class]['x_values']
        y = models_1D[model_class]['y_values']
        utils.assert_allclose(model(x), y, atol=self.eval_error)

    @pytest.mark.skipif('not HAS_SCIPY')
    @pytest.mark.parametrize(('model_class'), models_1D.keys())
    def test_fitter1D(self, model_class):
        """
        Test if the parametric model works with the fitter.
        """
        x_lim = models_1D[model_class]['x_lim']
        parameters = models_1D[model_class]['parameters']
        model = create_model(model_class, parameters)
        if isinstance(parameters, dict):
            parameters.pop('degree')
            parameters = parameters.values()
        if "log_fit" in models_1D[model_class]:
            if models_1D[model_class]['log_fit']:
                x = np.logspace(x_lim[0], x_lim[1], self.N)
        else:
            x = np.linspace(x_lim[0], x_lim[1], self.N)
        np.random.seed(0)
        # add 10% noise to the amplitude
        relative_noise_amplitude = 0.01
        #data = model(x) + relative_noise_amplitude * parameters[0] * (np.random.rand(self.N) - 0.5)
        data = (1 + relative_noise_amplitude * np.random.randn(len(x))) * model(x)
        fitter = fitting.NonLinearLSQFitter(model)
        fitter(x, data)

        # Only check parameters that were free in the fit
        fitted_parameters = [val
                             for (val, fixed) in zip(parameters, fitter.fixed)
                             if not fixed]
        utils.assert_allclose(fitter.fitparams, fitted_parameters,
                              atol=self.fit_error)

    @pytest.mark.parametrize(('model_class'), models_2D.keys())
    def test_input2D(self, model_class):
        """
        Test model with different input types.
        """
        parameters = models_2D[model_class]['parameters']
        model = create_model(model_class, parameters)
        model(self.x, self.y)
        model(self.x1, self.y1)
        model(self.x2, self.y2)

    @pytest.mark.parametrize(('model_class'), models_2D.keys())
    def test_eval2D(self, model_class):
        """
        Test model values add certain given points
        """
        parameters = models_2D[model_class]['parameters']
        model = create_model(model_class, parameters)
        x = models_2D[model_class]['x_values']
        y = models_2D[model_class]['y_values']
        z = models_2D[model_class]['z_values']
        assert np.all((np.abs(model(x, y) - z) < self.eval_error))

    @pytest.mark.skipif('not HAS_SCIPY')
    @pytest.mark.parametrize(('model_class'), models_2D.keys())
    def test_fitter2D(self, model_class):
        """
        Test if the parametric model works with the fitter.
        """
        x_lim = models_2D[model_class]['x_lim']
        y_lim = models_2D[model_class]['y_lim']

        parameters = models_2D[model_class]['parameters']
        model = create_model(model_class, parameters)
        if isinstance(parameters, dict):
            parameters.pop('degree')
            parameters = parameters.values()

        if "log_fit" in models_2D[model_class]:
            if models_2D[model_class]['log_fit']:
                x = np.logspace(x_lim[0], x_lim[1], self.N)
                y = np.logspace(y_lim[0], y_lim[1], self.N)
        else:
            x = np.linspace(x_lim[0], x_lim[1], self.N)
            y = np.linspace(y_lim[0], y_lim[1], self.N)
        xv, yv = np.meshgrid(x, y)

        np.random.seed(0)
        # add 10% noise to the amplitude
        data = model(xv, yv) + 0.1 * parameters[0] * (np.random.rand(self.N, self.N) - 0.5)
        fitter = fitting.NonLinearLSQFitter(model)
        fitter(xv, yv, data)
        assert np.all((np.abs(fitter.fitparams - np.array(parameters))
                        < self.fit_error))

    @pytest.mark.skipif('not HAS_SCIPY')
    @pytest.mark.parametrize(('model_class'), list(models_2D.keys()))
    def test_deriv_2D(self, model_class):
        """
        Test the derivative of a model by fitting with an estimated and
        analytical derivative
        """
        x_lim = models_2D[model_class]['x_lim']
        y_lim = models_2D[model_class]['y_lim']

        if model_class.deriv is None:
            pytest.skip("Derivative function is not defined for model.")
        if issubclass(model_class, (models.PolynomialModel, models.OrthoPolynomialBase)):
            pytest.skip("Skip testing derivative of polynomials.")

        if "log_fit" in models_2D[model_class]:
            if models_2D[model_class]['log_fit']:
                x = np.logspace(x_lim[0], x_lim[1], self.N)
                y = np.logspace(y_lim[0], y_lim[1], self.M)
        else:
            x = np.linspace(x_lim[0], x_lim[1], self.N)
            y = np.linspace(y_lim[0], y_lim[1], self.M)
        xv, yv = np.meshgrid(x, y)

        try:
            parameters = models_2D[model_class]['deriv_parameters']
            init_vals = models_2D[model_class]['deriv_initial']
        except KeyError:
            parameters = models_2D[model_class]['parameters']
            init_vals = parameters[:]
        model_with_deriv = create_model(model_class, init_vals, use_constraints=False)
        model_no_deriv = create_model(model_class, init_vals, use_constraints=False)

        # add 10% noise to the amplitude
        rsn = np.random.RandomState(1234567890)
        n = 0.1 * parameters[0] * (rsn.rand(self.M, self.N)-0.5)

        model = create_model(model_class, parameters, use_constraints=False)
        data = model(xv, yv) + n
        fitter_with_deriv = fitting.NonLinearLSQFitter(model_with_deriv)
        fitter_with_deriv(xv, yv, data)
        fitter_no_deriv = fitting.NonLinearLSQFitter(model_no_deriv)
        fitter_no_deriv(xv, yv, data, estimate_jacobian=True)
        utils.assert_allclose(model_with_deriv.parameters, model_no_deriv.parameters, rtol=0.1)

    @pytest.mark.skipif('not HAS_SCIPY')
    @pytest.mark.parametrize(('model_class'), list(models_1D.keys()))
    def test_deriv_1D(self, model_class):
        """
        Test the derivative of a model by comparing results with an estimated derivative
        """
        x_lim = models_1D[model_class]['x_lim']

        if model_class.deriv is None:
            pytest.skip("Derivative function is not defined for model.")
        if issubclass(model_class, (models.PolynomialModel, models.OrthoPolynomialBase)):
            pytest.skip("Skip testing derivative of polynomials.")

        if "log_fit" in models_1D[model_class]:
            if models_1D[model_class]['log_fit']:
                x = np.logspace(x_lim[0], x_lim[1], self.N)
        else:
            x = np.linspace(x_lim[0], x_lim[1], self.N)

        parameters = models_1D[model_class]['parameters']
        model_with_deriv = create_model(model_class, parameters, use_constraints=False)
        model_no_deriv = create_model(model_class, parameters, use_constraints=False)

        # add 10% noise to the amplitude
        rsn = np.random.RandomState(1234567890)
        n = 0.1 * parameters[0] * (rsn.rand(self.N) - 0.5)

        data = model_with_deriv(x) + n
        fitter_with_deriv = fitting.NonLinearLSQFitter(model_with_deriv)
        fitter_with_deriv(x, data)
        fitter_no_deriv = fitting.NonLinearLSQFitter(model_no_deriv)
        fitter_no_deriv(x, data, estimate_jacobian=True)
        utils.assert_allclose(model_with_deriv.parameters, model_no_deriv.parameters, atol=0.1)

def create_model(model_class, parameters, use_constraints=True):
    """
    Create instance of model class.
    """
    constraints = {}
    if issubclass(model_class, Parametric1DModel):
        if "requires_scipy" in models_1D[model_class] and not HAS_SCIPY:
            pytest.skip("SciPy not found")
        if use_constraints:
            if 'constraints' in models_1D[model_class]:
                constraints = models_1D[model_class]['constraints']
        return model_class(*parameters, **constraints)

    elif issubclass(model_class, Parametric2DModel):
        if "requires_scipy" in models_2D[model_class] and not HAS_SCIPY:
            pytest.skip("SciPy not found")
        if use_constraints:
            if 'constraints' in models_2D[model_class]:
                constraints = models_2D[model_class]['constraints']
        return model_class(*parameters, **constraints)

    elif issubclass(model_class, PolynomialModel):
        return model_class(**parameters)


def test_ShiftModel():
    # Shift by a scalar
    m = models.ShiftModel(42)
    assert m(0) == 42
    utils.assert_equal(m([1, 2]), [43, 44])

    # Shift by a list
    m = models.ShiftModel([42, 43])
    utils.assert_equal(m(0), [42, 43])
    utils.assert_equal(m([1, 2]), [[ 43,  44], [ 44,  45]])


def test_ScaleModel():
    # Scale by a scalar
    m = models.ScaleModel(42)
    assert m(0) == 0
    utils.assert_equal(m([1, 2]), [42, 84])

    # Scale by a list
    m = models.ScaleModel([42, 43])
    utils.assert_equal(m(0), [0, 0])
    utils.assert_equal(m([1, 2]), [[ 42,  43], [ 84,  86]])
