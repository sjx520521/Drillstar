import sys
import os
from PyQt5 import QtCore,QtGui, QtWidgets
from PyQt5.QtWidgets import QWidget,QApplication,QMainWindow,QTreeView,QAbstractItemView,QHeaderView,QStyleFactory,QMdiSubWindow,QMessageBox,QColorDialog
from PyQt5.QtCore import Qt, QModelIndex,pyqtSignal,QObject
from PyQt5.QtGui import QStandardItemModel, QStandardItem,QColor,QIcon
from datascope.ui.dataScope_ui import Ui_DataScope
import threading
from threading import Thread
from datascope.share_DataScope import ShareInfo
import time
import pandas as pd


class Win_DataScope(QMainWindow):
    closed = pyqtSignal()
    msg = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.ui = Ui_DataScope()
        self.ui.setupUi(self)
        self.init_TreeView()


        self.ui.btn_show.clicked.connect(self.on_Show)
        self.ui.action_MDIcascade.triggered.connect(self.on_MDIcascade)
        self.ui.action_MDItile.triggered.connect(self.on_MDItile)
        self.ui.action_MDIcloseAll.triggered.connect(self.on_MDIcloseAll)
        self.ui.action_TCPconnect.triggered.connect(self.on_Show_TCPconnect)
        self.ui.action_TCPclose.triggered.connect(self.on_CloseTCP)
        self.ui.action_NIDAQmx.triggered.connect(self.on_Show_NIDAQmx)
        self.ui.action_Control.triggered.connect(self.on_Show_Control)
        self.ui.action_check.triggered.connect(self.on_Check)

        self.ui.btn_Color.clicked.connect(self.on_SelectColor)
        self.msg.connect(self.on_ShowMsg)

        self.ui.action_TCPconnect.setIcon(QIcon("icon/连接.png"))
        self.ui.action_TCPclose.setIcon(QIcon("icon/断开.png"))
        self.ui.action_NIDAQmx.setIcon(QIcon("icon/NI_DAQ_connect.png"))
        self.ui.action_MDIcascade.setIcon(QIcon("icon/cascade.png"))
        self.ui.action_MDItile.setIcon(QIcon("icon/tile.png"))

        """test"""
        self.ui.action_NewProject.triggered.connect(self.on_Hecktest)


        # 初始是黑色
        self.col = QColor(0, 0, 0)
        self.ui.frame_Color.setStyleSheet(
            'QWidget {background-color: %s}' % self.col.name())

        self.ui.tE_msg.append("---->Data Scope启动，确保设备供电正常，请链接DAQ 和 测量短节的TCP！")


    def init_TreeView(self):
        #设置表头信息
        model = QStandardItemModel(self)
        model.setHorizontalHeaderLabels(['项目','信息'])

        #添加条目
        itemProject = QStandardItem('近钻头工程参数')
        model.appendRow(itemProject)
        model.setItem(0,1,QStandardItem('信息说明'))

        #添加子条目
        for key,value in ShareInfo.para_abbreviations_dict.items():
            itemChild = QStandardItem(key)
            itemProject.appendRow(itemChild)
            itemProject.setChild(itemChild.index().row(),1,QStandardItem(value))

        itemProject_peripheral = QStandardItem('施工参数')
        model.appendRow(itemProject_peripheral)
        model.setItem(1, 1, QStandardItem('信息说明'))
        for key,value in ShareInfo.paraPeripheral_abbreviations_dict.items():
            itemChild = QStandardItem(key)
            itemProject_peripheral.appendRow(itemChild)
            itemProject_peripheral.setChild(itemChild.index().row(),1,QStandardItem(value))


        treeView = self.ui.tv_project
        treeView.setModel(model)
        treeView.expandAll()
        treeView.setEditTriggers(QAbstractItemView.NoEditTriggers)

        treeView.selectionModel().currentChanged.connect(self.on_TreeView_CurrenChange)

    def on_TreeView_CurrenChange(self,current,previous):
        txt = '父级:[{}] '.format(str(current.parent().data()))

        txt += '当前选中:[(行{},列{})] '.format(current.row(), current.column())

        name = ''
        info = ''
        if current.column() == 0:
            name = str(current.data())
            info = str(current.sibling(current.row(), 1).data())
        else:
            name = str(current.sibling(current.row(), 0).data())
            info = str(current.data())

        txt += '名称:[{}]  信息:[{}]'.format(name, info)


        parentName = current.parent().data()
        childName = name
        abbreviationName = info
        number = current.row()
        if parentName == '近钻头工程参数':
            ShareInfo.selectPara_dict['group'] = 'A'
            ShareInfo.selectPara_dict['number'] = number
            ShareInfo.selectPara_dict['name'] = childName
            ShareInfo.selectPara_dict['abbreviation'] = abbreviationName

        elif parentName == '施工参数':
            ShareInfo.selectPara_dict['group'] = 'B'
            ShareInfo.selectPara_dict['number'] = number
            ShareInfo.selectPara_dict['name'] = childName
            ShareInfo.selectPara_dict['abbreviation'] = abbreviationName

        self.ui.gB_property.setTitle(childName)
        print(ShareInfo.selectPara_dict)
        # print(txt)

    def on_Show(self):
        from datascope.singlePlot import Win_SinglePlot
        self.k = self.ui.le_k.text()
        self.b = self.ui.le_b.text()
        self.l = self.ui.le_thickness.text()
        if ShareInfo.selectPara_dict['name'] in ShareInfo.para_Peripheral:
            if ShareInfo.ni_isConnect:
                self._openSubWin(ShareInfo.selectPara_dict['name'], Win_SinglePlot)
                subWindowFun = ShareInfo.subWinTable[ShareInfo.selectPara_dict['name']]['subWinFunc']
                subWindowFun.Modified_coordinate(ShareInfo.selectPara_dict['name'],self.k,self.b,self.col,self.l)
                self.msg.emit("---->打开窗口{}".format(ShareInfo.selectPara_dict['name']))
                # subWindowFun.Create_thread_NIDAQmx()
            else:
                QMessageBox.information(self, "错误", "未连接NI DAQmx / 未链接数据")
                self.msg.emit("---->错误：未连接NI DAQmx / 未链接数据")
        if ShareInfo.selectPara_dict['name'] in ShareInfo.para:
            if ShareInfo.tcp_isConnect:
                self._openSubWin(ShareInfo.selectPara_dict['name'], Win_SinglePlot)
                subWindowFun = ShareInfo.subWinTable[ShareInfo.selectPara_dict['name']]['subWinFunc']
                subWindowFun.Modified_coordinate(ShareInfo.selectPara_dict['name'],self.k,self.b,self.col,self.l)
                self.msg.emit("---->打开窗口{}".format(ShareInfo.selectPara_dict['name']))
                # subWindowFun.Create_thread_TCP()
            else:
                QMessageBox.information(self, "错误", "未连接 TCP")
                self.msg.emit("---->错误：未连接TCP")


    def on_Show_TCPconnect(self):
        from datascope.tcpConnect import Win_TCPconnect
        self._openSubWin("tcp", Win_TCPconnect)
        subWindow = ShareInfo.subWinTable['tcp']['subWinFunc']
        subWindow.msg_Signal.connect(self.on_ShowMsg)

    def on_Show_NIDAQmx(self):
        try:
            from datascope.niDAQmx import Win_NIDAQmx
            self._openSubWin("nidaqmx", Win_NIDAQmx)
            subWindow = ShareInfo.subWinTable['nidaqmx']['subWinFunc']
            subWindow.msg_Signal.connect(self.on_ShowMsg)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"NI DAQmx 模块打开失败：{e}")
        # subWindow.setWindowFlags(Qt.WindowType.WindowMinMaxButtonsHint | Qt.WindowType.WindowCloseButtonHint)

        # subWindow.setStyleSheet(
        #     'border-width:0px 0.2px 0.2px 0.2px;border-style: solid;')

        # border-width:0px 1px 1px 1px; 上 右 下 左
        # QtDesigner
        # 添加资源
        #     border-style: solid;
        #     border-width: 2px;
        #     border-color: darkgoldenrod

    def _openSubWin(self, FuncClass,WinFuncClass):
        """打开MDI子窗口的内部函数"""

        def createSubWin():
            """创造子窗口的子函数"""
            subWindow = QMdiSubWindow()  # 创建子窗口对象
            # 加载UI到子窗口界面
            subWinFunc = WinFuncClass()
            subWindow.setWidget(subWinFunc)
            subWindow.setAttribute(Qt.WA_DeleteOnClose)  # 点击退出释放窗口
            # 把子窗口加入到MDI区域
            self.ui.mdiArea_dataScope.addSubWindow(subWindow)
            # 存入表中，注意winFunc对象也要保存，不然对象没有引用，会销毁清除
            ShareInfo.subWinTable[str(FuncClass)] = {'subWindow': subWindow, 'subWinFunc': subWinFunc}
            print(ShareInfo.subWinTable)
            subWindow.show()  # 显示子窗口
            # 子窗口提到最上层，并且最大化
            # subWindow.setWindowState(Qt.WindowActive | Qt.WindowMaximized)
            subWindow.setWindowState(Qt.WindowActive)
            subWindow.setWindowTitle('Data Scope [{}]'.format(FuncClass))



        # 如果该功能类型 实例不存在
        if str(FuncClass) not in ShareInfo.subWinTable:
            # 创建实例
            createSubWin()
            return
        # 如果该功能类型已经存在，直接显示出来
        subWindow = ShareInfo.subWinTable[str(FuncClass)]['subWindow']
        try:
            subWindow.show()
            # 子窗口提到最上层，并且最大化
            subWindow.setWindowState(Qt.WindowActive)
        except:
            # show 异常原因肯定是用户手动关闭了该窗口，subWin对象已经不存在了
            createSubWin()


    def on_Check(self):
        print("****************测试****************")

        # 弹出颜色选择对话框, 返回值是QColor
        col = QColorDialog.getColor()

        # 检测用的选择是否合法(点击cancel就是非法,否则就是合法)
        if col.isValid():
            # 同前面一样,设置frame框架的颜色
            print(col.name())
            # self.frame.setStyleSheet(
            #     'QWidget {background-color: %s}'
            #     % col.name())

        print("---->窗口：{}".format(ShareInfo.subWinTable))
        pid = os.getpid()
        t = threading.current_thread()
        print(f"---->进程:[{pid}]线程:[{t.ident}-{t.name}]")
        length = len(threading.enumerate())
        print("---->线程：{}".format(threading.enumerate()))
        print('----->线程数：%d' % length)

    def on_MDIcascade(self):
        self.ui.mdiArea_dataScope.cascadeSubWindows()

    def on_MDItile(self):
        self.ui.mdiArea_dataScope.tileSubWindows()

    def on_MDIcloseAll(self):
        self.ui.mdiArea_dataScope.closeAllSubWindows()
        # self.subWinTable.clear()

    def on_CloseTCP(self):
        if "tcp" in ShareInfo.subWinTable:
            subWindowFun = ShareInfo.subWinTable["tcp"]['subWinFunc']
            subWindowFun.connect_TcpClose()

    def on_SelectColor(self):
        # 弹出颜色选择对话框, 返回值是QColor
        self.col = QColorDialog.getColor()
        if self.col.isValid():
            # 同前面一样,设置frame框架的颜色
            self.ui.frame_Color.setStyleSheet(
                'QWidget {background-color: %s}'
                % self.col.name())

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        if "nidaqmx" in ShareInfo.subWinTable:
            subWindowFun = ShareInfo.subWinTable['nidaqmx']['subWinFunc']
            subWindowFun.on_CloseTask()
            del ShareInfo.subWinTable["nidaqmx"]
        if "tcp" in ShareInfo.subWinTable:
            subWindowFun = ShareInfo.subWinTable['tcp']['subWinFunc']
            subWindowFun.connect_TcpClose()
            del ShareInfo.subWinTable["tcp"]

        self.closed.emit()  # 触发自定义关闭信号
        a0.accept()  # 允许窗口关闭

    def on_ShowMsg(self,str):
        self.ui.tE_msg.append(str)

    def on_Show_Control(self):
        from datascope.closedLoop_Control import Win_Control
        self.ControlUI = Win_Control()
        self.ControlUI.show()


    def on_Hecktest(self):
        from datascope.singlePlot import Win_SinglePlot
        filepath = 'C:/Users/XUAN/Desktop/地面模拟钻进实验装置测控系统研制/实验过程/拟定数据/092543_daq_b.csv'
        data = pd.read_csv(filepath)
        self._openSubWin('钻压', Win_SinglePlot)
        subWindowFun = ShareInfo.subWinTable['钻压']['subWinFunc']
        subWindowFun.on_heckPlot('钻压',data['钻压'])
        # self._openSubWin('扭矩', Win_SinglePlot)
        # subWindowFun = ShareInfo.subWinTable['扭矩']['subWinFunc']
        # subWindowFun.on_heckPlot('扭矩', data['扭矩'])
        self._openSubWin('转速', Win_SinglePlot)
        subWindowFun = ShareInfo.subWinTable['转速']['subWinFunc']
        subWindowFun.on_heckPlot('转速', data['转速'])
        # self._openSubWin('进尺', Win_SinglePlot)
        # subWindowFun = ShareInfo.subWinTable['进尺']['subWinFunc']
        # subWindowFun.on_heckPlot('进尺', data['进尺'])
        # self._openSubWin('施工钻压', Win_SinglePlot)
        # subWindowFun = ShareInfo.subWinTable['施工钻压']['subWinFunc']
        # subWindowFun.on_heckPlot('施工钻压', data['压力'])
        # self._openSubWin('切向', Win_SinglePlot)
        # subWindowFun = ShareInfo.subWinTable['切向']['subWinFunc']
        # subWindowFun.on_heckPlot('切向', data['切向'])
        # self._openSubWin('轴向', Win_SinglePlot)
        # subWindowFun = ShareInfo.subWinTable['轴向']['subWinFunc']
        # subWindowFun.on_heckPlot('轴向', data['轴向'])
        # self._openSubWin('法向', Win_SinglePlot)
        # subWindowFun = ShareInfo.subWinTable['法向']['subWinFunc']
        # subWindowFun.on_heckPlot('法向', data['法向'])
