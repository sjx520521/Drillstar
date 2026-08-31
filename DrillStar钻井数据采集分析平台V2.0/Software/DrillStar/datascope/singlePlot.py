import sys
import os
from PyQt5 import QtCore,QtGui, QtWidgets
from PyQt5.QtCore import Qt,QThread,pyqtSignal
from PyQt5.QtGui import QFont,QColor,QPen
from PyQt5.QtWidgets import QWidget,QApplication,QMainWindow,QAbstractItemView,QHeaderView,QMdiSubWindow,QMessageBox,QLabel,QHBoxLayout
from datascope.ui.singlePlot_ui import Ui_singlePlot
import pyqtgraph as pg
import numpy as np
from threading import Thread
from datascope.share_DataScope import ShareInfo
import inspect
import ctypes
import random


class Win_SinglePlot(QWidget):
    def __init__(self):
        super().__init__()
        self.ui = Ui_singlePlot()
        self.ui.setupUi(self)
        # self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        # self.setWindowFlag(Qt.WindowType.ForeignWindow)

        # win = pg.GraphicsLayoutWidget(show=True, title="Basic plotting examples")

        # Enable antialiasing for prettier plots
        pg.setConfigOptions(antialias=True)

        # self.X_Axis = pg.DateAxisItem(orientation='bottom', pen='k', textPen='k')
        self.X_Axis = pg.AxisItem(orientation='bottom', pen='k', textPen='k')
        self.X_Axis.setTickFont(QFont().setPixelSize(18))
        self.X_Axis.setStyle(tickTextOffset=5)
        self.X_Axis.setLabel('Time')

        self.Y_Axis = pg.AxisItem("left", pen='k', textPen='k')  # 设置Y轴
        self.Y_Axis.setTickFont(QFont().setPixelSize(18))
        self.Y_Axis.setStyle(tickTextOffset=5)
        self.Y_Axis.setLabel('钻压')


        pen = pg.mkPen(color=(255, 0, 0))

        self.widget = pg.PlotWidget(axisItems={"bottom": self.X_Axis, "left": self.Y_Axis}, ignoreBounds=True)
        self.widget.setBackground('w')
        self.widget.showGrid(x=True, y=True)  # 显示网格
        self.ui.Layout.addWidget(self.widget)

        self.widget.getPlotItem().sigRangeChanged.connect(self.on_limits_changed)
        # self.timer = pg.Qt.QtCore.QTimer()
        # self.timer.timeout.connect(self.UpdateData)
        # self.timer.start(50)

        self.data_list_ni = []
        self.data_list_tcp = []
        self.k = 1
        self.b = 0
        self.col = QColor(0, 0, 0)
        self.curve = self.widget.getPlotItem().plot()
        self.lineWidth = 1
        self.pen = QPen()
        self.pen.setColor(QColor(0,0,0))
        # self.pen.setWidth(self.lineWidth)



    def on_limits_changed(self):
        pass
        # self.widget.enableAutoRange(x=True,y=True)
        # self.widget.setAutoVisible(y=True,x=True)
        # x_range,y_range = self.widget.viewRange()
        # self.widget.setXRange(x_range[0],x_range[1],padding=0)
        # self.widget.setYRange(y_range[0],y_range[1],padding=0)


    def Modified_coordinate(self,Ylabel,k,b,col,l):
        print(Ylabel)
        self.WinTitleName = Ylabel
        self.p = self.widget.getPlotItem()
        self.Y_Axis.setLabel(Ylabel)
        self.p.setAxisItems(axisItems={"bottom": self.X_Axis, "left": self.Y_Axis})
        self.k = k
        self.b = b
        self.col = col
        self.pen.setColor(self.col)
        # self.pen.setWidth(int(l))


        # self.curve = self.p.plot()


    def Create_thread_TCP(self):
        self.thread_TCP_plot = Thread(target=self.Thread_TCP_PlotData, name = self.WinTitleName)
        self.thread_TCP_plot.start()

    def Create_thread_NIDAQmx(self):
        self.thread_NIDAQmx_plot = Thread(target=self.Thread_NIDAQmx_PlotData, name=self.WinTitleName)
        self.thread_NIDAQmx_plot.start()

    def Thread_NIDAQmx_PlotData(self):
        subWindowFun = ShareInfo.subWinTable['nidaqmx']['subWinFunc']
        while True:
            samplesAvailable = subWindowFun.get_samplesAvailable()
            if (samplesAvailable >= ShareInfo.numberOfSamples):
                if self.WinTitleName in ShareInfo.subWinTable:
                    val = ShareInfo.ni_vals[ShareInfo.paraPeripheral_get_NI_ai_count[self.WinTitleName]]
                    mean_val = sum(val) / len(val)
                    self.data_list_ni.append(float(mean_val))
                    self.curve.setData(self.data_list_ni,pen='k')

    def Thread_TCP_PlotData(self):
        # pass
        subWindowFun = ShareInfo.subWinTable['tcp']['subWinFunc']
        while True:
            if(subWindowFun.on_tcpGetRecv() != None):
                # vals = str(ShareInfo.tcp_vals).strip().split('|')
                vals = str(subWindowFun.on_tcpGetRecv()).strip().split('|')
                if self.WinTitleName in ShareInfo.subWinTable:
                    val = vals[ShareInfo.para_get_tcp[self.WinTitleName]]
                    self.data_list_tcp.append(float(val))
                    self.curve.setData(self.data_list_tcp,pen='k')

    def on_GetCurve(self):
        return self.curve

    def on_TCP_PlotData(self,Y):
        Y = float(self.k) * float(Y) + float(self.b)
        self.data_list_tcp.append(float(Y))
        self.curve.setData(self.data_list_tcp, pen=QColor(self.col))

    def on_NIDAQmx_PlotData(self,Y):
        Y = float(self.k) * float(Y) + float(self.b)
        self.data_list_ni.append(float(Y))
        self.curve.setData(self.data_list_ni, pen=QColor(self.col))

    #关闭线程
    def _async_raise(self,tid, exctype):
        """raises the exception, performs cleanup if needed"""
        tid = ctypes.c_long(tid)
        if not inspect.isclass(exctype):
            exctype = type(exctype)
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
        if res == 0:
            raise ValueError("invalid thread id")
        elif res != 1:
            # """if it returns a number greater than one, you're in trouble,
            # and you should call it again with exc=NULL to revert the effect"""
            ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
            raise SystemError("PyThreadState_SetAsyncExc failed")

    def stop_thread(self,thread):
        self._async_raise(thread.ident, SystemExit)

    def closeEvent(self, event):
        print("---->Window Close: "+self.WinTitleName)
        # if self.WinTitleName in ShareInfo.subWinTable:
        #     if self.WinTitleName in ShareInfo.para_Peripheral:
        #         self.stop_thread(self.thread_NIDAQmx_plot)
        #     if self.WinTitleName in ShareInfo.para:
        #         self.stop_thread(self.thread_TCP_plot)
        del ShareInfo.subWinTable[self.WinTitleName]
        self.close()


    def on_heckPlot(self,Ylabel,data):
        self.WinTitleName = Ylabel
        self.p = self.widget.getPlotItem()
        self.Y_Axis.setLabel(Ylabel)
        self.p.setAxisItems(axisItems={"bottom": self.X_Axis, "left": self.Y_Axis})

        self.widget.plot(data,pen=QColor(255,59,59))
