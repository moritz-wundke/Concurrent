# -*- coding: utf-8 -*-
"""
Sample application demostrating the implementation of a DNA Curve Analysis.
The implemnetation has been based on work from Christoph Gohlke (http://www.lfd.uci.edu/~gohlke/)

NOTE: The implementation is not finsihed and not working but demostrates the capabilities!

File: dnacurve.app.py
"""

from concurrent.framework.nodes.applicationnode import ApplicationNode
from concurrent.core.application.api import IApp
from concurrent.core.components.component import implements
from concurrent.core.async.task import Task
from concurrent.core.async.api import ITaskSystem
from concurrent.core.util.utils import is_digit, tprint
from concurrent.core.util.stats import time_push, time_pop

import sys
import os
import re
import math
import datetime
import warnings

import numpy

import time
import md5
import uuid
from uuid import UUID
import traceback

MAXLEN = 510  # maximum length of sequence

class DNACurveNode(ApplicationNode):
    """
    DNA Curve Analysis application
    """
    implements(IApp)
    
    def app_init(self):
        """
        Called just before the main entry. Used as the initialization point instead of the ctor
        """
        super(DNACurveNode, self).app_init()
    
    def app_main(self):
        """
        Applications main entry
        """
        return super(DNACurveNode, self).app_main()
    
    def get_task_system(self):
        """
        Called from the base class when we are connected to a MasterNode and we are 
        able to send computation tasks over
        """
        self.start_time = time.time()
        self.dna_system = DNACurveTaskSystem("ATGCAAATTG"*1000, "trifonov", name="Example", maxlen=1024*1024)
        return self.dna_system
    
    def work_finished(self, result, task_system):
        """
        Called when the work has been done, the results is what our ITaskSystem
        sent back to us. Check resukt for more info
        """
        # Reassamble result to be processed further
        try:
            print("Total time: {}".format(time.time() - self.start_time))
        except:
            traceback.print_exc()
        self.shutdown_main_loop()
    
    def push_tasksystem_response(self, result):
        """
        We just added a ITaskSystem on the framwork. Check result for more info
        """
        self.log.info("Tasks system send to computation framework")
    
    def push_tasksystem_failed(self, result):
        """
        We failed to push a ITaskSystem on the computation framework!
        """
        self.log.error("Tasks system failed to be send to framework!")
        # Check if the resuklt dict contains a traceback
        if "t" in result:
            self.log.error(result["t"])

class DNACurveTaskSystem(ITaskSystem):
    """
    The task system that is executed on the MasterNode and controls what jobs are required to be performed
    """
    
    p_coord = (  # cylindrical coordinates of 5' phosphate
        8.91,    # distance from axis
        -5.2,    # angle to roll axis
        2.08)    # distance from bp plane
    
    def __init__(self, sequence, model="trifonov", name="Untitled",
                 curvature_window=10, bend_window=2, curve_window=15,
                 maxlen=MAXLEN):
        """
        Default constructor used to initialize the base values. The ctor is
        executed on the ApplicationNode and not called on the MasterNode so we can 
        use it to initialize values.
        """
        super(DNACurveTaskSystem, self).__init__()
        
        if isinstance(model, Model):
            self.model = model
        else:
            self.model = Model(model)
        if isinstance(sequence, Sequence):
            self.sequence = sequence
        else:
            self.sequence = Sequence(sequence, name, maxlen=maxlen)
        if len(self.sequence) < self.model.order:
            raise ValueError(
                "sequence must be >%i nucleotides long" % self.model.order)
        elif len(self.sequence) > maxlen:
            warnings.warn("sequence is longer than %i nucleotides" % maxlen)

        assert 0 < curvature_window < 21
        assert 0 < bend_window < 4
        assert 9 < curve_window < 21
        self.windows = [curvature_window, bend_window, curve_window]
        self._limits = [10., 10., 10.]

        self.date = datetime.datetime.now()
        self.coordinates = numpy.zeros((5, len(self), 4), dtype=numpy.float64)
        self.curvature = numpy.zeros((3, len(self)), dtype=numpy.float64)
        self.scales = numpy.ones((3, 1), dtype=numpy.float64)
        
        # Create a number of jobs that will be processed
        self.jobs = 0
        self.finished_jobs = 0
        self.result = []
    
    def init_system(self, master):
        """
        Initialize the system
        """
        pass
    
    def generate_tasks(self, master):
        """
        From the analysis of the sequential version of the algorithm we conclude that each analysis of
        each sequence takes on average 0.006 seconds. We will split the workload so that we expect to
        send as much sequences to each worker so that the worker is busy for 1 second. This makes a
        total of 166 sequences for each task, the last tasks will vary in seuqences though.
        """
        job_list = []
        
        p = self.p_coord
        p = numpy.array((p[0] * math.cos(math.radians(p[1])),
                         p[0] * math.sin(math.radians(p[1])),
                         p[2]))
        
        xyz = self.coordinates
        xyz[0:3, :, 3] = 1.0  # homogeneous coordinates
        xyz[1, :, 0:3] = p  # 5' phosphate
        xyz[2, :, 0:3] = -p[0], p[1], -p[2]  # phosphate of antiparallel strand
        xyz[3, :, 2] = 1.0  # basepair normal vectors
        
        matrices = self.model.matrices      
        workload = []
        i = 0
        for i, seq in enumerate(dinuc_window(self.sequence, self.model.order)):
            #print(xyz[:4, :i+1, :])
            # Split workload
            workload.append(( xyz[:4, :i+1, :] , matrices[seq]))
            
            # Collect a set of 166 workloads
            if len(workload) == 1:
                job_list.append(DNACurveTask("dna_curve_{}".format(i), self.system_id, None, start = i, workload = workload))
                workload = []
        
        # Add last task with rest of workload
        if len(workload) > 0: 
            job_list.append(DNACurveTask("dna_curve_{}".format(i), self.system_id, None, start = i, workload = workload))

        self.jobs = len(job_list)
        self.start_time = time.time()
        return job_list
        
    def task_finished(self, master, task, result, error):
        """
        Called once a task has been performed
        """
        self.finished_jobs += 1
        if result:
            self.result += result
    
    def gather_result(self, master):
        """
        Once the system stated that it has finsihed the MasterNode will request the required results that
        are to be send to the originator. Returns a tuple like (result, Error)
        """
        print("Calculated in {} seconds!".format(time.time() - self.start_time))
        return (self.result, None)
    
    def is_complete(self, master):
        """
        Ask the system if the computation has finsihed. If not we will go on and generate more tasks. This
        gets performed every time a tasks finishes.
        """
        #print("%d -> %d" % (self.finished_jobs,self.jobs))
        # Wait for all tasks to finish
        return self.finished_jobs == self.jobs
    
    def __len__(self):
        """Return number of nucleotides in sequence."""
        return len(self.sequence)

    def __str__(self):
        """Return string representation of sequence and model."""
        return '%s\n\n%s\n' % (str(self.sequence), str(self.model))
    
    @property
    def name(self):
        return self.sequence.name
    
    def coordinates_post(self):
        """Calculate coordinates and normal vectors from sequence and model."""
        
        print(self.xyz)
        
        # Average direction vector of one helix turn,
        # calculated by smoothing the basepair normals
        if len(self.sequence) > 10:
            kernel = numpy.array([.5, 1, 1, 1, 1, 1, 1, 1, 1, 1, .5])
            kernel /= kernel.sum()
            for i in 0, 1, 2:
                self.xyz[4, :, i] = numpy.convolve(kernel, self.xyz[3, :, i], 'same')
            for i in range(5, len(self)-5):
                self.xyz[4, i, :] /= norm(self.xyz[4, i, :])
        
        self.coordinates = self.xyz

    def reorient(self):
        """Reorient coordinates."""
        xyz = self.coordinates[0, :, 0:3]  # helix axis
        xyz = xyz - xyz[-1]
        # assert start point is at origin
        assert numpy.allclose(xyz[-1], (0, 0, 0))
        # normalized end to end vector
        e = +xyz[0]
        e_len = norm(e)
        e /= e_len
        # point i of maximum distance to end to end line
        x = numpy.cross(e, xyz)
        x = numpy.sum(x*x, axis=1)
        i = numpy.argmax(x)
        x = math.sqrt(x[i])
        # distance of endpoint to xyz[i]
        w = norm(xyz[i])
        # distance of endpoint to point on end to end line nearest to xyz[i]
        u = math.sqrt(w*w - x*x)
        # find transformation matrix
        v0 = xyz[[0, i, -1]]
        v1 = numpy.array(((0, 0, 0), (e_len-u, 0, x), (e_len, 0, 0)))
        M = superimpose_matrix(v0, v1)
        self.coordinates = numpy.dot(self.coordinates, M.T)

    def center(self):
        """Center atomic coordinates at origin."""
        xyz = self.coordinates[0:3, :, 0:3]  # helix axis and P atoms
        low = numpy.min(numpy.min(xyz, axis=1), axis=0)
        upp = numpy.max(numpy.max(xyz, axis=1), axis=0)
        self._limits = (upp - low) / 2.0
        self.coordinates[0:3, :, 0:3] -= (low + self._limits)

    def curvature(self):
        """Calculate normalized curvature and bend angles."""
        dot = numpy.dot
        cross = numpy.cross
        arccos = numpy.arccos

        # curvature from radius
        window = self.windows[0]
        if len(self) >= 2*window:
            result = self.curvature[0, :]
            xyz = self.coordinates[0, :, 0:3]  # helix axis
            for i in range(window, len(self)-window):
                a, b, c = xyz[[i-window, i, i+window]]
                ab = b - a
                bc = c - b
                ac = c - a
                lab = norm(ab)
                lbc = norm(bc)
                lac = norm(ac)
                area = norm(cross(ab, ac))
                result[i] = (2.0*area) / (lab*lbc*lac)

        # local bend angles from basepair normals
        window = self.windows[1]
        if len(self) >= 2*window:
            normals = self.coordinates[3, :, 0:3]
            result = self.curvature[1, :]
            for i in range(window, len(self)-window):
                if not numpy.allclose(normals[i-window], normals[i+window]):
                    result[i] = arccos(dot(normals[i-window],
                                           normals[i+window]))

        # curvature angles from smoothed basepair normals
        window = self.windows[2]
        if len(self) >= 2*window:
            normals = self.coordinates[4, :, 0:3]
            result = self.curvature[2, :]
            for i in range(window, len(self)-window):
                if not numpy.allclose(normals[i-window], normals[i+window]):
                    result[i] = arccos(dot(normals[i-window],
                                           normals[i+window]))
        self.curvature = numpy.nan_to_num(self.curvature)

        # normalize relative to curvature in nucleosome
        self.scales[0] = 0.0234
        self.scales[1:] = 0.0234 * 2 * self.windows[2] * self.model.rise
        self.curvature /= self.scales

class DNACurveTask(Task):
    
    def __init__(self, name, system_id, **kwargs):
        Task.__init__(self, name, system_id, **kwargs)
        self.start = kwargs['start']
        self.workload = kwargs['workload']
        
    def __call__(self):
        """
        No try to find the hash
        """
        #tprint("Task [{}-{}] starting".format(os.getpid(), self.name))
        dot = numpy.dot
        results = []
        for work in self.workload:
            results.append(dot(work[0], work[1]))
        #tprint("Task [{}-{}] finished".format(os.getpid(), self.name))
        return (self.start, results)
    
    def finished(self, result, error):
        """
        Once the task is finished. Called on the MasterNode within the main thread once
        the node has recovered the result data.
        """
        #print("Task [{}] finished with: {}".format(self.name, result))
        pass

class Model(object):
    """N-mer DNA-bending model.

    Transformation parameters and matrices for all oligonucleotides of
    certain length.

    Attributes
    ----------
    name : str
        Human readable label.
    order : int
        Order of model, i.e. length of oligonucleotides.
        Order 2 is a dinucleotide model, order 3 a trinucleotide model etc.
    rise : float
        Displacement along the Z axis.
    twist : dict
        Rotation angle in deg about the Z axis for all oligonucleotides.
    roll : dict
        Rotation angle in deg about the Y axis for all oligonucleotides.
    tilt : dict
        Rotation angle in deg about the Z axis for all oligonucleotides.
    matrices : dict
        Homogeneous transformation matrices for all oligonucleotides.

    Examples
    --------
    >>> m = Model("AAWedge")
    >>> m = Model("Nucleosome")
    >>> m = Model(**Model.STRAIGHT)
    >>> m = Model(Model.CALLADINE, name="My Model", rise=4.0)
    >>> m.name == "My Model" and m.rise == 4.0
    True
    >>> m = Model(name="Test", rise=3.38,
    ...           oligo="AA AC AG AT CA GG CG GA GC TA".split(),
    ...           twist=(34.29, )*10, roll=(0., )*10, tilt=(0., )*10)
    >>> m.save("_test.dat")
    >>> m.twist == Model("_test.dat").twist
    True

    """
    STRAIGHT = dict(
        name = "Straight",
        oligo = "AA AC AG AT CA GG CG GA GC TA",
        twist = (360.0/10.5, ) * 10,
        roll =  (0.0, ) * 10,
        tilt =  (0.0, ) * 10,
        rise = 3.38)

    AAWEDGE = dict(
        name = "AA Wedge",
        oligo = "AA     AC    AG    AT    CA    GG     CG    GA    GC    TA",
        twist = (35.62, 34.4, 27.7, 31.5, 34.5, 33.67, 29.8, 36.9, 40.0, 36.0),
        roll =  (-8.40,  0.0,  0.0,  0.0,  0.0,   0.0,  0.0,  0.0,  0.0,  0.0),
        tilt =  ( 2.40,  0.0,  0.0,  0.0,  0.0,   0.0,  0.0,  0.0,  0.0,  0.0),
        rise = 3.38)

    CALLADINE = dict(
        # Nucleic Acids Res, 1994, 22(24), p 5498, Table 1, Model b.
        name = "Calladine & Drew",
        oligo = "AA    AC    AG    AT    CA    GG    CG    GA    GC    TA",
        twist = (35.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0),
        roll =  ( 0.0,  3.3,  3.3,  3.3,  3.3,  3.3,  3.3,  3.3,  3.3,  6.6),
        tilt =  ( 0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0),
        rise = 3.38)

    TRIFONOV = dict(
        # Nucleic Acids Res, 1994, 22(24), p 5498, Table 1, Model c.
        name = "Bolshoi & Trifonov",
        oligo = "AA     AC    AG    AT    CA    GG     CG    GA    GC    TA",
        twist = (35.62, 34.4, 27.7, 31.5, 34.5, 33.67, 29.8, 36.9, 40.0, 36.0),
        roll =  (-6.50, -0.9,  8.4,  2.6,  1.6,   1.2,  6.7, -2.7, -5.0,  0.9),
        tilt =  ( 3.20, -0.7, -0.3,  0.0,  3.1,  -1.8,  0.0, -4.6,  0.0,  0.0),
        rise = 3.38)

    DESANTIS = dict(
        # Nucleic Acids Res, 1994, 22(24), p 5498, Table 1, Model d.
        name = "Cacchione & De Santis",
        oligo = "AA    AC    AG    AT    CA    GG    CG    GA    GC    TA",
        twist = (35.9, 34.6, 35.6, 35.0, 34.5, 33.0, 33.7, 35.8, 33.3, 34.6),
        roll =  (-5.4, -2.4,  1.0, -7.3,  6.7,  1.3,  4.6,  2.0, -3.7,  8.0),
        tilt =  (-0.5, -2.7, -1.6,  0.0,  0.4, -0.6,  0.0, -1.7,  0.0,  0.0),
        rise = 3.38)

    REVERSED = dict(
        # Nucleic Acids Res, 1994, 22(24), p 5498, Table 1, Model e.
        name = "Reversed Calladine & Drew",
        oligo = "AA    AC    AG    AT    CA    GG    CG    GA    GC    TA",
        twist = (35.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0),
        roll =  ( 3.3,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -3.3),
        tilt =  ( 0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0),
        rise = 3.38)

    NUCLEOSOME = dict(
        # Nucleic Acids Res, 1994, 22(24), p 5498, Table 1, Model a.
        name = "Nucleosome Positioning",
        oligo = """
                AAA  ATA   AGA   ACA  TAA  TTA  TGA  TCA
                GAA  GTA   GGA   GCA  CAA  CTA  CGA  CCA
                AAT  ATT   AGT   ACT  TAT  TTT  TGT  TCT
                GAT  GTT   GGT   GCT  CAT  CTT  CGT  CCT
                AAG  ATG   AGG   ACG  TAG  TTG  TGG  TCG
                GAG  GTG   GGG   GCG  CAG  CTG  CGG  CCG
                AAC  ATC   AGC   ACC  TAC  TTC  TGC  TCC
                GAC  GTC   GGC   GCC  CAC  CTC  CGC  CCC""",
        roll = (0.0, 2.8,  3.3,  5.2, 2.0, 2.0, 5.4, 5.4,
                3.0, 3.7,  3.8,  5.4, 3.3, 2.2, 8.3, 5.4,
                0.7, 0.7,  5.8,  5.8, 2.8, 0.0, 5.2, 3.3,
                5.3, 3.7,  5.4,  7.5, 6.7, 5.2, 5.4, 5.4,
                5.2, 6.7,  5.4,  5.4, 2.2, 3.3, 5.4, 8.3,
                5.4, 6.5,  6.0,  7.5, 4.2, 4.2, 4.7, 4.7,
                3.7, 5.3,  7.5,  5.4, 3.7, 3.0, 6.0, 3.8,
                5.4, 5.4, 10.0, 10.0, 6.5, 5.4, 7.5, 6.0),
        twist = (34.3, ) * 64,
        tilt =  (0.0, ) * 64,
        rise = 3.38)

    def __init__(self, model=None, **kwargs):
        """Initialize instance from predefined model, file, or arguments.

        Parameters
        ----------
        model : various types
            Name of predefined model : str
                'straight', 'aawedge', 'trifonov', 'desantis', 'calladine',
                'reversed'
            Class or Dict:
                Instance containing model parameters
            Path name: str
                File containing model parameters
            None:
                Default model 'straight'
        name : str
            Human readable label.
        oligo : str or tuple
            Oligonucleotide sequences separated by whitespace or as tuple.
        twist : sequence of floats
            Twist values for given oligonucleotides in degrees.
        roll : sequence of floats
            Roll values for given oligonucleotides in degrees.
        tilt : sequence of floats
            Tilt values for given oligonucleotides in degrees.
        rise : float
            Rise value.

        """
        if model:
            for importfunction in (self._fromname, self._fromdict,
                                   self._fromclass, self._fromfile):
                try:
                    # import functions return dictionary or raise exception
                    model = importfunction(model)
                    break
                except Exception:
                    pass
            else:
                raise ValueError("can not initialize model from %s" % model)
        else:
            model = Model.STRAIGHT

        model.update(kwargs)

        try:
            self.oligos = model['oligo'].split()
        except Exception:
            self.oligos = model['oligo']
        self.order = len(self.oligos[0])
        self.name = str(model['name'][:32])
        self.rise = float(model['rise'])
        self.twist = dict(zip(self.oligos, model['twist']))
        self.roll = dict(zip(self.oligos, model['roll']))
        self.tilt = dict(zip(self.oligos, model['tilt']))

        self.matrices = {}
        for oligo in oligonucleotides(self.order):
            if not oligo in self.twist:
                c = complementary(oligo)
                self.twist[oligo] = self.twist[c]
                self.roll[oligo] = self.roll[c]
                self.tilt[oligo] = -self.tilt[c]  # tilt reverses sign
            self.matrices[oligo] = dinucleotide_matrix(
                self.rise, self.twist[oligo], self.roll[oligo],
                self.tilt[oligo]).T
        self.matrices[None] = dinucleotide_matrix(self.rise, 34.3, 0.0, 0.0).T

    def __str__(self):
        """Return string representation of model."""
        if self.order % 2:
            oligos = list(oligonucleotides(self.order))
        else:
            oligos = list(unique_oligos(self.order))

        def format_(items, formatstr="%5.2f", sep='  '):
            items = [formatstr % item for item in items]
            return "\n        ".join(sep.join(line) for line in chunks(items))

        result = [
            "%s\nRise    %.2f" % (self.name.split('\n')[0], self.rise),
            "Oligo   " + format_(oligos, "%s", ' ' * (7-self.order)),
            "Twist   " + format_(self.twist[i] for i in oligos),
            "Roll    " + format_(self.roll[i] for i in oligos),
            "Tilt    " + format_(self.tilt[i] for i in oligos)]
        return "\n".join(result)

    def _fromfile(self, path):
        """Return model parameters as dict from file."""
        d = {}
        with open(path, 'r') as fh:
            d['name'] = fh.readline().rstrip()
            d['rise'] = float(fh.readline().split()[-1])

            def readtuple(itemtype, line):
                alist = [itemtype(i) for i in line.split()[1:]]
                while 1:
                    line = fh.readline()
                    if line.startswith("     "):
                        alist.extend(itemtype(i) for i in line.split())
                    else:
                        break
                return tuple(alist), line

            d['oligo'], line = readtuple(str, fh.readline())
            d['twist'], line = readtuple(float, line)
            d['roll'], line = readtuple(float, line)
            d['tilt'], line = readtuple(float, line)
        return d

    def _fromname(self, name):
        """Return predefined model parameters as dict."""
        return getattr(Model, name.upper())

    def _fromclass(self, aclass):
        """Return model parameters as dict from class."""
        return dict((a, getattr(aclass, a)) for a in Model.STRAIGHT.keys())

    def _fromdict(self, adict):
        """Return model parameters as dict from dictionary."""
        for attr in Model.STRAIGHT.keys():
            adict[attr]  # validation
        return adict

    def save(self, path):
        """Save model to file."""
        with open(path, 'w') as fh:
            fh.write(str(self))


class Sequence(object):
    """DNA nucleotide sequence.

    Attributes
    ----------
    name : str
        Human readable label.
    comment : str
        Single line description of sequence.
    string : str
        Sequence string containing only ATCG.

    Notes
    -----
    FASTA files must contain ``>name<space>comment<newline>sequence``.
    SEQ files must contain ``name<newline>comment<newline>sequence``.
    Nucleotides other than ATCG are ignored.

    Examples
    --------
    >>> Sequence("0AxT-C:G a`t~c&g\t")[:]
    'ATCGATCG'
    >>> seq = Sequence("ATGCAAATTG"*3, name="Test")
    >>> seq == "ATGCAAATTG"*3
    True
    >>> seq == None
    False
    >>> seq.save("_test.seq")
    >>> seq == Sequence("_test.seq")
    True

    """
    # Proc Natl Acad Sci USA, 1983, 80(24), p 7678, Fig 1
    KINETOPLAST = """
        GATCTAGACT AGACGCTATC GATAAAGTTT AAACAGTACA ACTATCGTGC TACTCACCTG
        TTGCCAAACA TTGCAAAAAT GCAAAATTGG GCTTGTGGAC GCGGAGAGAA TTCCCAAAAA
        TGTCAAAAAA TAGGCAAAAA ATGCCAAAAA TCCCAAACTT TTTAGGTCCC TCAGGTAGGG
        GCGTTCTCCG AAAACCGAAA AATGCATGCA GAAACCCCGT TCAAAAATCG GCCAAAATCG
        CCATTTTTTC AATTTTCGTG TGAAACTAGG GGTTGGTGTA AAATAGGGGT GGGGCTCCCC
        GGGGTAATTC TGGAAATTCG GGCCCTCAGG CTAGACCGGT CAAAATTAGG CCTCCTGACC
        CGTATATTTT TGGATTTCTA AATTTTGTGG CTTTAGATGT GGGAGATTTG GATC"""

    OUT_OF_PHASE_AAAAAA = "CGCGCGCAAAAAACG"
    PHASED_AAAAAA = "CGAAAAAACG"
    PHASED_GGGCCC = "GAGGGCCCTA"

    def __init__(self, arg, name="Untitled", comment="", maxlen=1024*1024):
        """Initialize instance from nucleotide sequence string or file name."""
        self.name = name
        self.comment = comment
        self._sequence = ''
        if os.path.isfile(arg):
            self._fromfile(arg, maxsize=maxlen*2)
            self.fname = os.path.split(arg)[1]
        else:
            self._sequence = arg
            self.fname = None

        # clean name and comment
        for sep in (None, '|', ',', ';', '>', '<'):
            self.name = self.name.split(sep, 1)[0]
        self.name = self.name[:32]
        self.comment = (comment + ' ').splitlines()[0].strip()

        # remove all but ATCG from sequence
        nucls = dict(zip('ATCGatcg', 'ATCGATCG'))
        self._sequence = ''.join(nucls.get(c, '') for c in self._sequence)
        # limit length of sequence
        if maxlen and len(self._sequence) > maxlen:
            warnings.warn("sequence truncated to %i nucleotides" % maxlen)
            self._sequence = self._sequence[:maxlen]
        if not self._sequence:
            raise ValueError("not a valid sequence")

    def _fromfile(self, path, maxsize=-1):
        """Read name, comment and sequence from file."""
        with open(path, 'r') as fh:
            firstline = fh.readline().rstrip()
            if firstline.startswith('>'):  # Fasta format
                self.name, self.comment = (firstline[1:] + ' ').split(' ', 1)
            elif firstline:
                self.name = firstline
                self.comment = fh.readline()
            self._sequence = fh.read(maxsize)

    def save(self, path):
        """Save sequence to file."""
        with open(path, 'w') as fh:
            fh.write(str(self))

    @property
    def string(self):
        """Return sequence as string."""
        return self._sequence

    def format(self, block=10, line=6):
        """Return string of sequence formatted in blocks and lines."""
        lines = chunks(chunks(self._sequence, block), line)
        formatstr = "%%%ii %%s" % (len("%i" % ((len(lines)-1)*block*line, )), )
        for i, s in enumerate(lines):
            lines[i] = formatstr % (i*line*block, ' '.join(s))
        return "\n".join(lines)

    def __getitem__(self, key):
        """Return nucleotide at position."""
        return self._sequence[key]

    def __len__(self):
        """Return number of nucleotides in the sequence."""
        return len(self._sequence)

    def __iter__(self):
        """Return iterator over nucleotides."""
        return iter(self._sequence)

    def __eq__(self, other):
        """Return result of sequence comparison."""
        try:
            return self._sequence == other[:]
        except Exception:
            return False

    def __str__(self):
        """Return string representation of sequence."""
        return "%s\n%s\n%s" % (self.name, self.comment, self.format())


_COMPLEMENTARY = dict(zip('ATCG', 'TAGC'))


def complementary(sequence):
    """Return complementary sequence.

    Examples
    --------
    >>> complementary('AT CG')
    'CGAT'

    """
    c = _COMPLEMENTARY
    return ''.join(c.get(nucleotide, '') for nucleotide in reversed(sequence))


def oligonucleotides(length, nucleotides="AGCT"):
    """Generate all oligonucleotide sequences of length.

    Examples
    --------
    >>> " ".join(oligonucleotides(2))
    'AA AG AC AT GA GG GC GT CA CG CC CT TA TG TC TT'

    """
    def rloop(length, part):
        if length:
            length -= 1
            for nucleotide in nucleotides:
                for oligo in rloop(length, part+nucleotide):
                    yield oligo
        else:
            yield part

    return rloop(length, '')


def unique_oligos(length, nucleotides="AGCT"):
    """Generate all unique oligonucleotide sequences of length.

    Examples
    --------
    >>> " ".join(unique_oligos(2))
    'AA AG AC AT GA GG GC CA CG TA'

    """
    s = set()
    for oligo in oligonucleotides(length, nucleotides):
        if oligo in s:
            s.remove(oligo)
        else:
            s.add(complementary(oligo))
            yield oligo


def chunks(sequence, size=10):
    """Return sequence in chunks of size.

    Examples
    --------
    >>> chunks('ATCG'*4, 10)
    ['ATCGATCGAT', 'CGATCG']

    """
    return [sequence[i:i+size] for i in range(0, len(sequence), size)]


def overlapping_chunks(sequence, size, overlap):
    """Return iterator over overlapping chunks of sequence.

    Examples
    --------
    >>> list(overlapping_chunks('ATCG'*4, 4, 2))
    [(0, 'ATCGATCG'), (4, 'ATCGATCG'), (8, 'ATCGATCG')]

    """
    index = 0
    while index < len(sequence)-2*overlap:
        yield index, sequence[index:index+size+2*overlap]
        index += size


def dinuc_window(sequence, size):
    """Return window of nucleotides around each dinucleotide in sequence.

    Return None if window overlaps border.

    Examples
    --------
    >>> list(dinuc_window('ATCG', 2))
    ['AT', 'TC', 'CG']
    >>> list(dinuc_window('ATCG', 3))
    ['ATC', 'TCG', None]
    >>> list(dinuc_window('ATCG', 4))
    [None, 'ATCG', None]

    """
    assert 1 < size <= len(sequence)
    border = size // 2
    for i in range(0, border-1):
        yield None
    for i in range(0, len(sequence)-size+1):
        yield sequence[i:i+size]
    for i in range(len(sequence)-size+border, len(sequence)-1):
        yield None


def dinucleotide_matrix(rise, twist, roll, tilt):
    """Return transformation matrix to move from one nucleotide to next."""
    twist = math.radians(twist)
    sinw = math.sin(twist)
    cosw = math.cos(twist)
    roll = math.radians(-roll)
    sinr = math.sin(roll)
    cosr = math.cos(roll)
    tilt = math.radians(-tilt)
    sint = math.sin(tilt)
    cost = math.cos(tilt)
    return numpy.array((
        (cost*cosw, sinr*sint*cosw-cosr*sinw, cosr*sint*cosw+sinr*sinw,  0.0),
        (cost*sinw, sinr*sint*sinw+cosr*cosw, cosr*sint*sinw-sinr*cosw,  0.0),
        (    -sint,                sinr*cost,                cosr*cost, rise),
        (      0.0,                      0.0,                      0.0,  1.0)),
        dtype=numpy.float64)


def superimpose_matrix(v0, v1):
    """Return matrix to transform given vector set to second vector set."""
    # move centroids to origin
    t0 = numpy.mean(v0, axis=0)
    t1 = numpy.mean(v1, axis=0)
    v0 -= t0
    v1 -= t1
    # SVD of covariance matrix
    u, _, vh = numpy.linalg.svd(numpy.dot(v1.T, v0))
    # rotation matrix from SVD orthonormal bases
    R = numpy.dot(u, vh)
    if numpy.linalg.det(R) < 0.0:
        # correct reflections
        R -= numpy.outer(u[:, 2], vh[2, :] * 2.0)
    # homogeneous transformation matrix
    M = numpy.identity(4, dtype=numpy.float64)
    T = numpy.identity(4, dtype=numpy.float64)
    M[0:3, 0:3] = R
    M[:3, 3] = t1
    T[0:3, 3] = -t0
    return numpy.dot(M, T)


def norm(vector):
    """Return length of vector, i.e. its euclidean norm."""
    # return numpy.linalg.norm(vector)
    return numpy.sqrt(numpy.dot(vector, vector))