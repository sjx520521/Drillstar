import os
import nidaqmx
from nidaqmx import constants
from nidaqmx.constants import TerminalConfiguration
from datascope.ui.niDAQmx_ui import Ui_NIDAQmx
from datascope.share_DataScope import ShareInfo
from PyQt5.QtWidgets import QWidget,QMessageBox
from PyQt5.QtCore import Qt,pyqtSignal
from PyQt5 import QtGui
from threading import Thread
import inspect
import ctypes


class Win_NIDAQmx(QWidget):
    msg_Signal = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.ui = Ui_NIDAQmx()
        self.ui.setupUi(self)

        self.ui.btn_CreateTask.clicked.connect(self.on_startTask)
        self.ui.btn_connectData.clicked.connect(self.on_runTask)
        self.ui.btn_CloseTask.clicked.connect(self.on_CloseTask)
        self.ui.btn_connectData.setEnabled(False)

        ShareInfo.physicalChannel = str(self.ui.lE_Channel.text())



    def on_startTask(self):
        #Create and start task
        try:
            self.task = nidaqmx.Task()
            #RSE输入。单端输入 。0-10V
            self.task.ai_channels.add_ai_voltage_chan(ShareInfo.physicalChannel,min_val=ShareInfo.minVoltage,max_val=ShareInfo.maxVoltage,terminal_config=TerminalConfiguration.RSE)
            self.task.timing.cfg_samp_clk_timing(ShareInfo.sampleRate,sample_mode=constants.AcquisitionType.CONTINUOUS,samps_per_chan=ShareInfo.numberOfSamples*3)
            self.task.start()
            QMessageBox.information(self, "成功", "连接 NI DAQmx 成功")
            self.msg_Signal.emit("---->连接 NI DAQmx 成功")
            self.ui.btn_connectData.setEnabled(True)
        except Exception as e:
            print("---->Create nidaqmx task fall：" + str(e))
            QMessageBox.critical(self,"错误","连接 NI DAQmx 错误")
            self.msg_Signal.emit("---->连接 NI DAQmx 错误")

    def on_runTask(self):
        self.thread_runTask = Thread(target=self.Thread_runTask,name="nidaqmx")
        self.thread_runTask.start()
        QMessageBox.information(self, "成功", "链接数据成功")
        self.msg_Signal.emit("---->链接数据成功")
        ShareInfo.ni_isConnect = True


    def get_samplesAvailable(self):
        return self.task._in_stream.avail_samp_per_chan

    def Thread_runTask(self):
        # Check if task needs to update the graph
        while True:
            samplesAvailable = self.task._in_stream.avail_samp_per_chan
            if (samplesAvailable >= ShareInfo.numberOfSamples):
                vals = self.task.read(ShareInfo.numberOfSamples)
                for i in range(5):
                    if ShareInfo.para_Peripheral[i] in ShareInfo.subWinTable:
                        subWindowFun = ShareInfo.subWinTable[ShareInfo.para_Peripheral[i]]['subWinFunc']
                        val = vals[ShareInfo.paraPeripheral_get_NI_ai_count[ShareInfo.para_Peripheral[i]]]
                        mean_val = sum(val) / len(val)
                        subWindowFun.on_NIDAQmx_PlotData(mean_val)
                # ShareInfo.ni_vals = vals


    def on_CloseTask(self):
        try:
            try:
                self.stop_thread(self.thread_connectServer)
            except Exception as e:
                print("---->NIDAQmx Thread close error: {}".format(e))
            self.task.stop()
            self.task.close()
            ShareInfo.ni_isConnect = False
            self.ui.btn_connectData.setEnabled(False)
            print("---->Close Task success")
            self.msg_Signal.emit("---->关闭采集卡任务成功")
        except Exception as e:
            print("---->Close Task with error: " + str(e))
            # self.msg_Signal.emit("---->关闭采集卡任务失败")

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

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        subWindow = ShareInfo.subWinTable['nidaqmx']['subWindow']
        subWindow.hide()
        a0.ignore()