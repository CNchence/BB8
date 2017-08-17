"""Provides ConvLayer class for using in CNNs.

ConvLayer provides interface for building convolutional layers in CNNs.
ConvLayerParams is the parametrization of these ConvLayer layers.

Copyright 2017 Mahdi Rad, ICG,
Graz University of Technology <mahdi.rad@icg.tugraz.at>

This file is part of BB8.

BB8 is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

BB8 is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with BB8.  If not, see <http://www.gnu.org/licenses/>.
"""

import numpy
import theano
import theano.sandbox.neighbours
import theano.tensor as T
from theano.tensor.signal.pool import pool_2d
from theano.tensor.nnet import conv2d
from net.layerparams import LayerParams
from activations import ReLU

__author__ = "Mahdi Rad <mahdi.rad@icg.tugraz.at>, Paul Wohlhart <wohlhart@icg.tugraz.at>, Markus Oberweger <oberweger@icg.tugraz.at>"
__copyright__ = "Copyright 2017, ICG, Graz University of Technology, Austria"
__credits__ = ["Mahdi Rad", "Paul Wohlhart", "Markus Oberweger"]
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Mahdi Rad"
__email__ = "mahdi.rad@icg.tugraz.at, radmahdi@gmail.com"
__status__ = "Development"


class ConvPoolLayerParams(LayerParams):

    def __init__(self, inputDim=None, nFilters=None, filterDim=None, activation=T.tanh, poolsize=(1, 1), poolType=0,
                 filter_shape=None, image_shape=None, outputDim=None, stride=(1, 1), border_mode='valid'):
        """
        :type filter_shape: tuple or list of length 4
        :param filter_shape: (number of filters, num inputVar feature maps, filter height,filter width)

        :type image_shape: tuple or list of length 4
        :param image_shape: (batch size, num inputVar feature maps, image height, image width)

        :type poolsize: tuple or list of length 2
        :param poolsize: the downsampling (pooling) factor (#rows,#cols)
        """

        super(ConvPoolLayerParams, self).__init__(inputDim, outputDim)

        self._nFilters = nFilters
        self._filterDim = filterDim
        self._poolsize = poolsize
        self._poolType = poolType
        self._filter_shape = filter_shape
        self._image_shape = image_shape
        self._activation = activation
        self._stride = stride
        self._border_mode = border_mode
        self.update()

    @property
    def filter_shape(self):
        return self._filter_shape

    @property
    def image_shape(self):
        return self._image_shape

    @property
    def stride(self):
        return self._stride

    @stride.setter
    def stride(self, value):
        self._stride = value
        self.update()

    @property
    def border_mode(self):
        return self._border_mode

    @border_mode.setter
    def border_mode(self, value):
        self._border_mode = value
        self.update()

    @property
    def nFilters(self):
        return self._nFilters

    @nFilters.setter
    def nFilters(self, value):
        self._nFilters = value
        self.update()

    @property
    def filterDim(self):
        return self._filterDim

    @filterDim.setter
    def filterDim(self, value):
        self._filterDim = value
        self.update()

    @property
    def poolsize(self):
        return self._poolsize

    @poolsize.setter
    def poolsize(self, value):
        self._poolsize = value
        self.update()

    @property
    def poolType(self):
        return self._poolType

    @property
    def activation(self):
        return self._activation

    def update(self):
        """
        calc image_shape,
        """
        self._filter_shape = (self._nFilters,
                              self._inputDim[1],
                              self._filterDim[1],
                              self._filterDim[0])
        self._image_shape = self._inputDim

        if self._border_mode == 'valid':
            self._outputDim = (self._inputDim[0],   # batch_size
                               self._nFilters,      # number of kernels
                               (self._inputDim[2] - self._filterDim[0] + 1),   # output H
                               (self._inputDim[3] - self._filterDim[1] + 1))   # output W
        elif self._border_mode == 'full':
            self._outputDim = (self._inputDim[0],   # batch_size
                               self._nFilters,      # number of kernels
                               (self._inputDim[2] + self._filterDim[0] - 1),   # output H
                               (self._inputDim[3] + self._filterDim[1] - 1))   # output W
        elif self._border_mode == 'same':
            self._outputDim = (self._inputDim[0],   # batch_size
                               self._nFilters,      # number of kernels
                               self._inputDim[2],   # output H
                               self._inputDim[3])   # output W
        else:
            raise ValueError("Unknown border mode")

        # correct stride
        self._outputDim = list(self._outputDim)
        self._outputDim[2] = int(numpy.ceil(self._outputDim[2] / float(self._stride[0]))) // self._poolsize[0]
        self._outputDim[3] = int(numpy.ceil(self._outputDim[3] / float(self._stride[1]))) // self._poolsize[1]
        self._outputDim = tuple(self._outputDim)

        # no pooling required
        if(self._poolsize[0] == 1) and (self._poolsize[1] == 1):
            self._poolType = -1

    def getMemoryRequirement(self):
        """
        Get memory requirements of weights
        :return: memory requirement
        """
        return (numpy.prod(self.filter_shape) + self.filter_shape[0]) * 4  # sizeof(theano.config.floatX)

    def getOutputRange(self):
        """
        Get output range of layer
        :return: output range as tuple
        """
        if self._activation == T.tanh:
            return [-1, 1]
        elif self._activation == T.nnet.sigmoid:
            return [0, 1]
        elif self._activation == ReLU:
            return [0, numpy.inf]
        else:
            return [-numpy.inf, numpy.inf]


class ConvPoolLayer(object):
    """
    Pool Layer of a convolutional network
    copy of LeNetConvPoolLayer from deeplearning.net tutorials
    """

    def __init__(self, rng, inputVar, cfgParams, copyLayer=None, layerNum=None):
        """
        Allocate a LeNetConvPoolLayer with shared variable internal parameters.

        :type rng: numpy.random.RandomState
        :param rng: a random number generator used to initialize weights

        :type inputVar: theano.tensor.dtensor4
        :param inputVar: symbolic image tensor, of shape image_shape

        :type cfgParams: ConvPoolLayerParams
        """

        assert isinstance(cfgParams, ConvPoolLayerParams)

        floatX = theano.config.floatX  # @UndefinedVariable

        filter_shape = cfgParams.filter_shape
        image_shape = cfgParams.image_shape
        filter_stride = cfgParams.stride
        poolsize = cfgParams.poolsize
        poolType = cfgParams.poolType
        activation = cfgParams.activation
        inputDim = cfgParams.inputDim
        border_mode = cfgParams.border_mode

        self.cfgParams = cfgParams
        self.layerNum = layerNum

        assert image_shape[1] == filter_shape[1]
        self.inputVar = inputVar

        # there are "num inputVar feature maps * filter height * filter width"
        # inputs to each hidden unit
        fan_in = numpy.prod(filter_shape[1:])
        # each unit in the lower layer receives a gradient from:
        # "num output feature maps * filter height * filter width" / pooling size
        fan_out = (filter_shape[0] * numpy.prod(filter_shape[2:]) / numpy.prod(poolsize) / numpy.prod(filter_stride))

        if not (copyLayer is None):
            self.W = copyLayer.W
        else:
            W_bound = 1. / (fan_in + fan_out)
            wInitVals = numpy.asarray(rng.uniform(low=-W_bound, high=W_bound, size=filter_shape), dtype=floatX)
            self.W = theano.shared(wInitVals, borrow=True, name='convW{}'.format(layerNum))

        # the bias is a 1D tensor -- one bias per output feature map
        if not (copyLayer is None):
            self.b = copyLayer.b
        else:
            b_values = numpy.zeros((filter_shape[0],), dtype=floatX) 
            self.b = theano.shared(value=b_values, borrow=True, name='convB{}'.format(layerNum))
        if border_mode == 'same':
            # convolve inputVar feature maps with filters
            conv_out = conv2d(input=inputVar,
                              filters=self.W,
                              filter_shape=filter_shape,
                              input_shape=image_shape,
                              subsample=filter_stride,
                              border_mode='full')

            # perform full convolution and crop output of input size
            offset_2 = filter_shape[2]//2
            offset_3 = filter_shape[3]//2
            conv_out = conv_out[:, :, offset_2:offset_2+image_shape[2], offset_3:offset_3+image_shape[3]]
        else:
            conv_out = conv2d(input=inputVar,
                              filters=self.W,
                              filter_shape=filter_shape,
                              input_shape=image_shape,
                              subsample=filter_stride,
                              border_mode=border_mode)

        # downsample each feature map individually, using maxpooling
        if poolType == 0:
            # using maxpooling
            if poolsize != (1, 1):
                pooled_out = pool_2d(input=conv_out, ds=poolsize, ignore_border=True)
            else:
                pooled_out = conv_out
        elif poolType == 1:
            # using average pooling
            pooled_out = theano.sandbox.neighbours.images2neibs(ten4=conv_out, neib_shape=poolsize, mode='ignore_borders').mean(axis=-1)
            new_shape = T.cast(T.join(0, conv_out.shape[:-2], T.as_tensor([conv_out.shape[2]//poolsize[0]]),
                                      T.as_tensor([conv_out.shape[3]//poolsize[1]])), 'int64')
            pooled_out = T.reshape(pooled_out, new_shape, ndim=4)
        elif poolType == -1:
            # no pooling at all
            pooled_out = conv_out

        # add the bias term. Since the bias is a vector (1D array), we first reshape it to a tensor of shape
        # (1,n_filters,1,1). Each bias will thus be broadcasted across mini-batches and feature map width & height
        lin_output = pooled_out + self.b.dimshuffle('x', 0, 'x', 'x')
        self.output = (lin_output if activation is None
                       else activation(lin_output))

        self.output.name = 'output_layer_{}'.format(self.layerNum)

        # store parameters of this layer
        self.params = [self.W, self.b]
        self.weights = [self.W]

    def __str__(self):
        """
        Print configuration of layer
        :return: configuration string
        """
        return "inputDim {}, outputDim {}, filterDim {}, nFilters {}, activation {}, stride {}, border_mode {}, pool_type {}, pool_size {}".format(self.cfgParams.inputDim, self.cfgParams.outputDim, self.cfgParams.filterDim,
                                                                  self.cfgParams.nFilters, self.cfgParams.activation_str, self.cfgParams.stride, self.cfgParams.border_mode, self.cfgParams.poolType, self.cfgParams.poolsize)
