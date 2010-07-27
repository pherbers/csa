#
#  This file is part of the Connection-Set Algebra (CSA).
#  Copyright (C) 2010 Mikael Djurfeldt
#
#  CSA is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  CSA is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import math
import random
import copy

import connset as cs
import valueset as vs
import _elementary


class Random (cs.Operator):
    def __mul__ (self, valueSet):
        return ValueSetRandomMask (valueSet)
    
    def __call__ (self, p = None, N = None, fanIn = None, fanOut = None):
        if p != None:
            assert N == None and fanIn == None and fanOut == None, \
                   'inconsistent parameters'
            return _elementary.ConstantRandomMask (p)
        elif N != None:
            assert fanIn == None and fanOut == None, \
                   'inconsistent parameters'
            return _elementary.SampleNRandomOperator (N)
        elif fanIn != None:
            assert fanOut == None, \
                   'inconsistent parameters'
            return _elementary.FanInRandomOperator (fanIn)
        elif fanOut != None:
            return _elementary.FanOutRandomOperator (fanOut)
        assert False, 'inconsistent parameters'


class ValueSetRandomMask (cs.Mask):
    def __init__ (self, valueSet):
        cs.Mask.__init__ (self)
        self.valueSet = valueSet
        self.state = random.getstate ()

    def startIteration (self, state):
        random.setstate (self.state)
        return self

    def iterator (self, low0, high0, low1, high1, state):
        for j in xrange (low1, high1):
            for i in xrange (low0, high0):
                if random.random () < self.valueSet (i, j):
                    yield (i, j)


class Disc (cs.Operator):
    def __init__ (self, r):
        self.r = r

    def __mul__ (self, metric):
        return DiscMask (self.r, metric)


class DiscMask (cs.Mask):
    def __init__ (self, r, metric):
        cs.Mask.__init__ (self)
        self.r = r
        self.metric = metric

    def iterator (self, low0, high0, low1, high1, state):
        for j in xrange (low1, high1):
            for i in xrange (low0, high0):
                if self.metric (i, j) < self.r:
                    yield (i, j)


class Gaussian (cs.Operator):
    def __init__ (self, sigma, cutoff):
        self.sigma = sigma
        self.cutoff = cutoff
        
    def __mul__ (self, metric):
        return GaussianValueSet (self.sigma, self.cutoff, metric)


class GaussianValueSet (vs.ValueSet):
    def __init__ (self, sigma, cutoff, metric):
        self.sigma22 = 2* sigma * sigma
        self.cutoff = cutoff
        self.metric = metric

    def __call__ (self, i, j):
        d = self.metric (i, j)
        return math.exp (- d * d / self.sigma22) if d < self.cutoff else 0.0


class Block (cs.Operator):
    def __init__ (self, M, N):
        self.M = M
        self.N = N

    def __mul__ (self, other):
        c = cs.coerceCSet (other)
        if isinstance (c, cs.Mask):
            return BlockMask (self.M, self.N, c)
        else:
            return cs.ConnectionSet (BlockCSet (self.M, self.N, c))


class BlockMask (cs.Mask):
    def __init__ (self, M, N, mask):
        cs.Mask.__init__ (self)
        self.M = M
        self.N = N
        self.m = mask

    def iterator (self, low0, high0, low1, high1, state):
        maskIter =  self.m.iterator (low0 / self.M,
                                     (high0 + self.M - 1) / self.M,
                                     low1 / self.N,
                                     (high1 + self.N - 1) / self.N,
                                     state)
        try:
            pre = []
            (i, j) = maskIter.next ()
            while True:
                # collect connections in one connection matrix column
                post = j
                while j == post:
                    pre.append (i)
                    (i, j) = maskIter.next ()

                # generate blocks for the column
                for jj in xrange (max (self.N * post, low1),
                                  min (self.N * (post + 1), high1)):
                    for k in pre:
                        for ii in xrange (max (self.M * k, low0),
                                          min (self.M * (k + 1), high0)):
                            yield (ii, jj)
                pre = []
        except StopIteration:
            if pre:
                # generate blocks for the last column
                for jj in xrange (max (self.N * post, low1),
                                  min (self.N * (post + 1), high1)):
                    for k in pre:
                        for ii in xrange (max (self.M * k, low0),
                                          min (self.M * (k + 1), high0)):
                            yield (ii, jj)


class Transpose (cs.Operator):
    def __mul__ (self, other):
        c = cs.coerceCSet (other)
        if isinstance (c, cs.Mask):
            return other.transpose ()
        else:
            return cs.ConnectionSet (other.transpose ())


class Shift (cs.Operator):
    def __init__ (self, M, N):
        self.M = M
        self.N = N

    def __mul__ (self, other):
        c = cs.coerceCSet (other)
        if isinstance (c, cs.Mask):
            return other.shift (self.M, self.N)
        else:
            return cs.ConnectionSet (other.shift (self.M, self.N))


class Fix (cs.Operator):
    def __mul__ (self, other):
        c = cs.coerceCSet (other)
        if isinstance (c, cs.Mask):
            return FixedMask (other)
        else:
            return cs.ConnectionSet (FixedCSet (other))


class FixedMask (cs.FiniteMask):
    def __init__ (self, mask):
        cs.FiniteMask.__init__ (self)
        ls = []
        for c in mask:
            ls.append (c)
        self.connections = ls
        targets = map (cs.target, ls)
        self.low0 = min (ls)[0]
        self.high0 = max (ls)[0] + 1
        self.low1 = min (targets)
        self.high1 = max (targets) + 1

    def iterator (self, low0, high0, low1, high1, state):
        if not self.isBoundedBy (low0, high0, low1, high1):
            return iter (self.connections)
        else:
            return self.boundedIterator (low0, high0, low1, high1)

    def boundedIterator (self, low0, high0, low1, high1):
        for c in self.connections:
            if low0 <= c[0] and c[0] < high0 \
               and low1 <= c[1] and c[1] < high1:
                yield c
