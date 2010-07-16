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

import random
import numpy
import copy

import connset as cs


class OneToOne (cs.Mask):
    def __init__ (self):
        cs.Mask.__init__ (self)
    
    def iterator (self, low0, high0, low1, high1, state):
        for i in xrange (max (low0, low1), min (high0, high1)):
            yield (i, i)


class ConstantRandomMask (cs.Mask):
    def __init__ (self, p):
        cs.Mask.__init__ (self)
        self.p = p
        self.state = random.getstate ()

    def startIteration (self, state):
        random.setstate (self.state)
        return self

    def iterator (self, low0, high0, low1, high1, state):
        for j in xrange (low1, high1):
            for i in xrange (low0, high0):
                if random.random () < self.p:
                    yield (i, j)


class SampleNRandomOperator (cs.Operator):
    def __init__ (self, N):
        self.N = N

    def __mul__ (self, other):
        assert isinstance (other, cs.Finite) \
               and isinstance (other, cs.Mask), \
               'expected finite mask'
        return SampleNRandomMask (self.N, other)


class SampleNRandomMask (cs.Finite,cs.Mask):
    # The algorithm based on first sampling the number of connections
    # per partition has been arrived at through discussions with Hans
    # Ekkehard Plesser.
    #
    def __init__ (self, N, mask):
        cs.Mask.__init__ (self)
        self.N = N
        assert isinstance (mask, cs.FiniteISetMask), \
               'SampleNRandomMask only operates on FiniteISetMask:s'
        self.mask = mask
        self.randomState = random.getstate ()
        self.npRandomState = numpy.random.get_state ()

    def bounds (self):
        return self.mask.bounds ()

    def startIteration (self, state):
        obj = copy.copy (self)  # local state: N, N0, perTarget, sources
        random.setstate (self.randomState)
        obj.isPartitioned = False
        if 'partitions' in state:
            obj.isPartitioned = True
            partitions = map (self.mask.intersection, state['partitions'])
            sizes = map (len, partitions)
            total = sum (sizes)
            
            # The following yields the same result on all processes.
            # We should add a seed function to the CSA.
            if 'seed' in state:
                seed = state['seed']
            else:
                seed = 'SampleNRandomMask'
            numpy.random.seed (hash (seed))
            
            N = numpy.random.multinomial (self.N, numpy.array (sizes) \
                                           / float (total))
            obj.N = N[state['selected']]
            obj.mask = partitions[state['selected']]
            assert isinstance (obj.mask, cs.FiniteISetMask), \
                   'SampleNRandomMask iterator only handles finite IntervalSetMask partitions'
        obj.mask = obj.mask.startIteration (state)
        obj.N0 = len (obj.mask.set0)
        obj.lastBound0 = False
        N1 = len (obj.mask.set1)
        numpy.random.set_state (self.npRandomState)
        obj.perTarget = numpy.random.multinomial (obj.N, [1.0 / N1] * N1)
        return obj

    def iterator (self, low0, high0, low1, high1, state):
        m = self.mask.set1.count (0, low1)
        
        if self.isPartitioned and m > 0:
            # "replacement" for a proper random.jumpahead (n)
            # This is required so that different partitions of this
            # mask aren't produced using the same stream of random
            # numbers.
            random.seed (random.getrandbits (32) + m)
            
        if self.lastBound0 != (low0, high0):
            self.lastBound0 = (low0, high0)
            self.sources = []
            for i in self.mask.set0.boundedIterator (low0, high0):
                self.sources.append (i)

        nSources = len (self.sources)
        for j in self.mask.set1.boundedIterator (low1, high1):
            s = []
            for k in xrange (0, self.perTarget[m]):
                i = random.randint (0, self.N0 - 1)
                if i < nSources:
                    s.append (self.sources[i])
            s.sort ()
            for i in s:
                yield (i, j)
            m += 1


class FanInRandomOperator (cs.Operator):
    def __init__ (self, fanIn):
        self.fanIn = fanIn

    def __mul__ (self, other):
        assert isinstance (other, cs.Finite) \
               and isinstance (other, cs.Mask), \
               'expected finite mask'
        return FanInRandomMask (self.fanIn, other)


# This code is copied and modified from SampleNRandomMask
# *fixme* refactor code and eliminate code duplication
class FanInRandomMask (cs.Finite,cs.Mask):
    # The algorithm based on first sampling the number of connections
    # per partition has been arrived at through discussions with Hans
    # Ekkehard Plesser.
    #
    def __init__ (self, fanIn, mask):
        cs.Mask.__init__ (self)
        self.fanIn = fanIn
        assert isinstance (mask, cs.FiniteISetMask), \
               'FanInRandomMask only operates on FiniteISetMask:s'
        self.mask = mask
        self.randomState = random.getstate ()

    def bounds (self):
        return self.mask.bounds ()

    def startIteration (self, state):
        obj = copy.copy (self)  # local state: N, N0, perTarget, sources
        random.setstate (self.randomState)
        obj.isPartitioned = False
        if 'partitions' in state:
            obj.isPartitioned = True
            partitions = map (self.mask.intersection, state['partitions'])
            
            # The following yields the same result on all processes.
            # We should add a seed function to the CSA.
            if 'seed' in state:
                seed = state['seed']
            else:
                seed = 'FanInRandomMask'
            numpy.random.seed (hash (seed))

            selected = state['selected']
            obj.mask = partitions[selected]
            assert isinstance (obj.mask, cs.FiniteISetMask), \
                   'FanInRandomMask iterator only handles finite IntervalSetMask partitions'
        obj.mask = obj.mask.startIteration (state)
        obj.N0 = len (obj.mask.set0)
        obj.lastBound0 = False
        if obj.isPartitioned:
            obj.perTarget = []
            for j in obj.mask.set1:
                size = 0
                sourceDist = numpy.zeros (len (partitions))
                for k in xrange (len (partitions)):
                    if j in partitions[k].set1:
                        sourceDist[k] = len (partitions[k].set0)
                sourceDist /= sum (sourceDist)
                dist = numpy.random.multinomial (self.fanIn, sourceDist)
                obj.perTarget.append (dist[selected])
        else:
            obj.perTarget = [self.fanIn] * len (obj.mask.set1)
        return obj

    def iterator (self, low0, high0, low1, high1, state):
        m = self.mask.set1.count (0, low1)
        
        if self.isPartitioned and m > 0:
            # "replacement" for a proper random.jumpahead (n)
            # This is required so that different partitions of this
            # mask aren't produced using the same stream of random
            # numbers.
            random.seed (random.getrandbits (32) + m)
            
        if self.lastBound0 != (low0, high0):
            self.lastBound0 = (low0, high0)
            self.sources = []
            for i in self.mask.set0.boundedIterator (low0, high0):
                self.sources.append (i)

        nSources = len (self.sources)
        for j in self.mask.set1.boundedIterator (low1, high1):
            s = []
            for k in xrange (0, self.perTarget[m]):
                i = random.randint (0, self.N0 - 1)
                if i < nSources:
                    s.append (self.sources[i])
            s.sort ()
            for i in s:
                yield (i, j)
            m += 1


class FanOutRandomOperator (cs.Operator):
    def __init__ (self, fanOut):
        self.fanOut = fanOut

    def __mul__ (self, other):
        assert isinstance (other, cs.Finite) \
               and isinstance (other, cs.Mask), \
               'expected finite mask'
        return FanInRandomMask (self.fanOut, other.transpose ()).transpose ()
