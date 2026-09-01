import sys
import os
from PyQt5 import QtCore,QtGui, QtWidgets
from PyQt5.QtCore import Qt,QThread,pyqtSignal
from PyQt5.QtWidgets import QWidget,QApplication,QMainWindow,QAbstractItemView,QHeaderView,QMdiSubWindow,QMessageBox,QLabel,QHBoxLayout
from threading import Thread
import threading
import socket
from datascope.singlePlot import Win_SinglePlot
import inspect
import ctypes
from datascope.ui.tcp_ui import Ui_tcp
from datascope.share_DataScope import ShareInfo
import time
import datetime

class Win_TCPconnect(QWidget):
    msg_Signal = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.ui = Ui_tcp()
        self.ui.setupUi(self)

        self.ui.le_IPaddress.setText("192.168.1.1")
        self.ui.le_port.setText('8899')

        self.ui.btn_listeningPort.clicked.connect(self.connect_TcpServer)

    def connect_TcpServer(self):
        self.ip = self.ui.le_IPaddress.text()
        self.port = int(self.ui.le_port.text())
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # self.sock.bind((self.ip,self.port))
            self.sock.connect(((self.ip,self.port)))
        except Exception as e:
            QMessageBox.critical(self, '错误', 'TCP连接错误！')
            self.msg_Signal.emit("---->TCP连接错误！")
            ShareInfo.tcp_isConnect = False
            print("---->TCP connect fall: " + str(e))
            self.msg_Signal.emit("---->TCP connect fall:{}".format(e))
        else:
            self.thread_connectServer = Thread(target=self.Thread_tcpConnect_deal,name='TCP')
            self.thread_connectServer.start()
            ShareInfo.tcp_isConnect = True
            ShareInfo.time_start = datetime.datetime.now()
            other_StyleTime = ShareInfo.time_start.strftime("%Y-%m-%d %H:%M:%S")
            print("---->当前时间：{}".format(other_StyleTime))
            self.msg_Signal.emit("---->当前时间：{}".format(other_StyleTime))
            QMessageBox.information(self,'正确','连接{}成功'.format(self.ip))
            self.msg_Signal.emit("---->TCP 连接{}成功}".format(self.ip))

    def Thread_tcpConnect_deal(self):
        while True:
            response = self.sock.recv(4096)
            # print(response.decode())
            # ShareInfo.tcp_vals.append(response.decode())
            ShareInfo.tcp_vals = response.decode()
            if(response.decode() != None):
                vals = str(response.decode()).strip().split('|')
                for i in range(9):
                    if ShareInfo.para[i] in ShareInfo.subWinTable:
                        subWindowFun = ShareInfo.subWinTable[ShareInfo.para[i]]['subWinFunc']
                        val = vals[ShareInfo.para_get_tcp[ShareInfo.para[i]]]
                        subWindowFun.on_TCP_PlotData(val)

    def on_tcpGetRecv(self):
        return self.sock.recv(4096).decode()

    def connect_TcpClose(self):
        try:
            self.on_CloseTCPthread()
            self.sock.close()
            ShareInfo.tcp_isConnect = False
            print("---->TCP connect close")
            self.msg_Signal.emit("---->TCP connect close success")
        except Exception as e:
            print("---->TCP connect close error: " + str(e))
            self.msg_Signal.emit("---->TCP connect close error:{} ".format(e))

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        subWindow = ShareInfo.subWinTable['tcp']['subWindow']
        subWindow.hide()
        a0.ignore()
        # self.stop_thread(self.thread_connectServer)

    def on_CloseTCPthread(self):
        try:
            self.stop_thread(self.thread_connectServer)
        except Exception as e:
            print("---->TCP Thread close error: {}".format(e))

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