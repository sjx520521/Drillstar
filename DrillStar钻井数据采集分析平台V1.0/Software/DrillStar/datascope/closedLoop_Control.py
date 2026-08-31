import sys
import os
from PyQt5 import QtCore,QtGui, QtWidgets
from PyQt5.QtCore import Qt,QThread,pyqtSignal
from PyQt5.QtGui import QFont,QColor,QPen
from PyQt5.QtWidgets import QWidget,QApplication,QMainWindow,QAbstractItemView,QHeaderView,QMdiSubWindow,QMessageBox,QLabel,QHBoxLayout
from datascope.ui.control_ui import Ui_Control
import pyqtgraph as pg
import numpy as np
from threading import Thread
from datascope.share_DataScope import ShareInfo
import inspect
import ctypes
import nidaqmx
from nidaqmx.constants import LineGrouping



class Win_Control(QWidget):
    def __init__(self):
        super().__init__()
        self.ui = Ui_Control()
        self.ui.setupUi(self)
        self.setWindowTitle("PID Control")

        self.ui.btn_Show.clicked.connect(self.on_control)
        self.ui.btn_Set.clicked.connect(self.on_set)
        self.ui.btn_Stop.clicked.connect(self.on_stop)

        """heck"""
        # self.ui.lN_WOB_infliction.display(24.7)
        # self.ui.lN_RPM_infliction.display(75.3)
        # self.ui.lN_WOB_Bit.display(20.4)
        # self.ui.lN_RPM_Bit.display(74.8)

    def on_control(self):
        try:
            self.task = nidaqmx.Task()
            self.task.do_channels.add_do_chan(ShareInfo.do_port, line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
            self.task.start()
            print("---->Create nidaqmx task success DO")
        except Exception as e:
            print("---->Create nidaqmx task fall：{}".format(e))

    def on_set(self):
        try:
            print("N Lines 1 Sample Boolean Write : True ")
            print(self.task.write(True))
        except nidaqmx.DaqError as e:
            print("---->N Lines 1 Sample Boolean Write (Error Expected): {}".format(e))

    def on_stop(self):
        try:
            print("N Lines 1 Sample Boolean Write : False ")
            print(self.task.write(False))
        except nidaqmx.DaqError as e:
            print("---->N Lines 1 Sample Boolean Write (Error Expected): {}".format(e))

            # print("1 Channel N Lines 1 Sample Unsigned Integer Write: ")
            # print(self.task.write(8))
            #
            # print("1 Channel N Lines N Samples Unsigned Integer Write: ")
            # print(self.task.write([1, 2, 4, 8], auto_start=True))

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        self.task.stop()
        self.task.close()