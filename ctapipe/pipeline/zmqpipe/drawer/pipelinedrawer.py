# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""
classes used to display pipeline workload on a Qt.QWidget
"""
from graphviz import Digraph
from PyQt4 import QtCore, QtGui
from PyQt4.QtGui import QWidget
from PyQt4.QtGui import QPainter
from PyQt4.QtGui import QLabel
from PyQt4.QtGui import QColor
from PyQt4.QtCore import QPoint
from PyQt4.QtGui import QPixmap
from PyQt4.QtGui import QGridLayout
from PyQt4.QtCore import Qt
from time import sleep
import sys
from ctapipe.pipeline.zmqpipe.drawer.table_queue import TableQueue

class StagerRep():

    """
    class to represent a Stager, Consumer and Producer figure
    Parameters
    ----------
    name  : str
    next_steps : list(str)
    running : bool
    nb_job_done : int
    """

    def __init__(self,name,next_steps=list(),running=False,nb_job_done=0):
        self.name = name
        self.next_steps = next_steps
        self.running = running
        self.nb_job_done = nb_job_done


    def __repr__(self):
        """  called by the repr() built-in function and by string conversions
        (reverse quotes) to compute the "official" string representation of
        an object.  """
        return (self.name + ' -> running: '+
            str(self.running)+ '-> nb_job_done: '+
            str(self.nb_job_done) + '-> next_steps' +
            str(self.next_steps))

    def get_name_and_queue(self):
        """
        return a string containing name and queue_size
        """
        return str(self.name) + ' ' + str(self.queue_size)

class PipelineDrawer(QWidget):

    """
    class that displays pipeline workload
    It receives pipeline information thanks to pipechange method
    """
    blue_cta = QColor(1, 39, 118)
    mygreen = QColor(65, 205, 85)

    def __init__(self, statusBar):
        super(PipelineDrawer, self).__init__()
        self.point_size = 1
        self.initUI()
        # self.steps contains all pipeline steps (Producer, Stager, consumer)
        self.steps = list()
        # self.config_time stores time when pipeline send its config
        self.config_time = 0.
        self.statusBar = statusBar
        self.zoom = 2
        self.queues=dict()


    def initUI(self):
        #self.setGeometry(300, 300, 280, 170)
        self.setWindowTitle('PIPELINE')
        self.show()

    def paintEvent(self, e):
        """This event handler is reimplemented in this subclass to receive
         paint events passed in event. A paint event is a request to repaint all
         or part of a widget. It can happen for one of the following reasons:
         repaint() or update() was invoked,the widget was obscured and has
         now been uncovered, or many other reasons. """
        if self.steps is None:
            return
        qp = QPainter()
        qp.begin(self)
        diagram = self.build_graph()
        diagram_bytes = diagram.pipe('png')
        pixmap = QPixmap()
        pixmap.loadFromData(diagram_bytes)
        png_size = pixmap.size()
        line = 20
        qp.drawText(0,line,"QUEUES")
        line+=20
        qp.drawText(0,line,"_________")
        line+=20
        for stage,queue in self.queues.items():
            queue_txt = '{:>} '.format(stage.split('_router')[0] + " "+ queue)
            qp.drawText(0,line,queue_txt)
            line+=20
        qp.drawPixmap(150,0,self.size().width()-150,self.size().height(),pixmap)
        qp.end()


    def pipechange(self, topic, msg):
        """Called by ZmqSub instance when it receives zmq message from pipeline
        Update pipeline state (self.steps) and force to update drawing
        Parameters
        ----------
        topic : str
            Define what has changed in pipeline:
            -GUI_GRAPH -> Full pipeline config ( step, router ...) is send
            -GUI_STAGER_CHANGE   -> A pipeline stager has changed
            -GUI_CONSUMER_CHANGE -> A pipeline consumer has changed
            -GUI_PRODUCER_CHANGE -> The pipeline producer
             has changed
            -GUI_ROUTER_CHANGE   -> A pipeline Router has changed
        msg : list
            contains informations to update
        """
        # Full pipeline config change
        if topic == b'GUI_GRAPH':
            config_time, receiv_steps = msg
            if config_time != self.config_time:
                self.steps = receiv_steps
                self.config_time = config_time
        # Stager or Producer or Consumer state changes

        if self.steps is not None and (topic == b'GUI_STAGER_CHANGE' or
                                        topic == b'GUI_CONSUMER_CHANGE' or
                                        topic == b'GUI_PRODUCER_CHANGE'):
            self.step_change(msg)
        # Force to update drawing

        if topic == b'GUI_ROUTER_CHANGE':
            self.router_change(msg)


        self.update()

    def step_change(self, msg):
        """Find which pipeline step has changed, and update its corresponding
        StagerRep
        Parameters
        ----------
        msg: list
            contains step name, step running flag and step nb_job_done
            receiv_steps: list of GUIStepInfo describing pipeline contents
        """
        name, running, nb_job_done = msg
        for step in self.steps:
            foo = name.split('$$thread')[0]
            if step.name == foo:
                step.running = running
                step.nb_job_done = nb_job_done
                break

    def router_change(self, msg):
            """Find which pipeline router has changed, and update its corresponding
            RouterRep
            Parameters
            ----------
            msg: list
                contains router name and router queue
            receiv_levels: list of StepInfo describing pipeline contents
            """
            name, queue = msg
            self.queues[name]=queue

    def build_graph(self):
        """
        Return a graphiz.Digraph
        """
        g = Digraph('test', format='png')
        for step in  self.steps:
            if step.running:
                g.node(step.name,color='lightblue2', style='filled')
            else:
                g.node(step.name)

        for step in self.steps:
            for next_step_name in step.next_steps:
                next_step = self.get_step_by_name(next_step_name)
                g.edge(step.name, next_step.name)
        #g.edge_attr.update(arrowhead='vee', arrowsize='2')
        return g

    def get_step_by_name(self, name):
        ''' Find a PipeStep in self.producer_step or  self.stager_steps or
        self.consumer_step
        Return: PipeStep if found, otherwise None
        '''
        for step in self.steps:
            if step.name == name:
                return step
        return None
