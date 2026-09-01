import pandas as pd
from threading import Thread, Event
from PyQt5 import QtGui
from PyQt5.QtWidgets import (
    QMainWindow, QAbstractItemView, QMdiSubWindow, QMessageBox,
    QMenu, QAction
)
from PyQt5.QtCore import Qt, pyqtSignal, QAbstractTableModel, QTimer, QThread
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from database.ui.dataBase_ui import Ui_DataBase
from database.share_DataBase import ShareInfo
from database.sqlConnect import Win_SQlconnect
from database.sqlUpload import Win_SQlupload
from database.sqlDownload import Win_SQldownload


class Win_DataBase(QMainWindow):
    signal_Loading = pyqtSignal()
    signal_Msg = pyqtSignal(str, int)
    signal_UpdateTable = pyqtSignal(pd.DataFrame)  # 新增：更新表格的信号
    closed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.ui = Ui_DataBase()
        self.ui.setupUi(self)
        self.ui.splitter.setSizes([300, 700])

        # 修复线程初始化（原__int__是笔误）
        self.loading_QThread = myThread()  # 测试线程

        # 线程控制标记
        self.load_thread = None  # 加载数据的线程对象
        self.stop_thread_event = Event()  # 线程停止事件

        self.signal_Msg.connect(self.on_Msg)
        self.signal_UpdateTable.connect(self._update_table_view)  # 绑定更新表格的信号
        self.ui.treeView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ui.tV_DataTable.setEditTriggers(QAbstractItemView.NoEditTriggers)  # 不可编辑
        self.ui.tV_DataTable.setSelectionBehavior(QAbstractItemView.SelectRows)  # 设置只有行选中

        # 为QTreeView添加右键菜单支持（核心修改1）
        self.ui.treeView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.treeView.customContextMenuRequested.connect(self._show_tree_right_menu)

        # 绑定原有信号
        self.ui.action_ConnectSQL.triggered.connect(self.on_SQLconnect)
        self.ui.action_UploadData.triggered.connect(self.on_SQLupload)
        self.ui.action_DownloadData.triggered.connect(self.on_SQLdownload)
        self.ui.action_RUN.triggered.connect(self.on_Console)

    def _update_table_view(self, df):
        """主线程中更新表格（避免子线程操作UI）"""
        # 检查是否需要停止更新（表已被删除）
        if self.stop_thread_event.is_set():
            return
        self.model = pandasModel(df)
        self.ui.tV_DataTable.setModel(self.model)

    def on_initTree(self):
        """更新表树结构"""
        # 强制重新获取表列表，确保数据实时性
        ShareInfo.get_all_tables()
        # 设置表头信息
        self.model = QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels(['表'])
        root = self.model.invisibleRootItem()
        for i in ShareInfo.sql_Tables:
            # 兼容不同格式的表名（如元组/字符串）
            table_name = str(i[0]) if isinstance(i, (tuple, list)) else str(i)
            child1 = QStandardItem(table_name)
            root.appendRow(child1)

        self.ui.treeView.setModel(self.model)
        self.ui.treeView.clicked.connect(self.on_TreeClicked)
        self.ui.treeView.doubleClicked.connect(self.on_TreeDoubleClicked)

    def _show_tree_right_menu(self, pos):
        """QTreeView右键菜单：显示删除表选项"""
        # 获取右键点击的索引
        index = self.ui.treeView.indexAt(pos)
        if not index.isValid():
            return  # 点击空白处，不显示菜单

        # 获取表名
        tablename = index.data()
        if not tablename:
            return

        # 创建右键菜单
        menu = QMenu(self.ui.treeView)
        # 添加删除表动作
        delete_action = QAction("删除表", self)
        delete_action.triggered.connect(lambda: self._on_delete_table(tablename))
        menu.addAction(delete_action)

        # 转换为全局坐标显示菜单
        global_pos = self.ui.treeView.mapToGlobal(pos)
        menu.exec_(global_pos)

    def _on_delete_table(self, tablename):
        """处理删除表的逻辑：增加资源释放和线程停止"""
        # 禁用UI操作，避免并发冲突
        self.ui.treeView.setEnabled(False)
        self.ui.tV_DataTable.setEnabled(False)

        try:
            # 停止正在运行的加载线程
            self.stop_thread_event.set()
            if self.load_thread and self.load_thread.is_alive():
                self.load_thread.join(timeout=1)  # 等待线程结束，超时1秒

            # 二次确认弹窗
            reply = QMessageBox.question(
                self,
                "确认删除",
                f"是否确定删除表【{tablename}】？\n此操作不可恢复！",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                # 调用删除表方法（内部已处理连接的创建和关闭）
                success, msg = ShareInfo.delete_table(tablename)
                if success:
                    QMessageBox.information(self, "成功", msg)
                    # 强制刷新表树（重新获取表列表并更新UI）
                    self.on_initTree()
                    # 清空数据表格
                    self.ui.tV_DataTable.setModel(None)
                    # 清空表信息标签
                    self.ui.label_row.setText("")
                    self.ui.label_length.setText("")
                    self.ui.label_CreateDate.setText("")
                    # 发送消息
                    self.signal_Msg.emit(f"---->表 {tablename} 删除成功", 0)
                else:
                    QMessageBox.critical(self, "错误", msg)
                    self.signal_Msg.emit(f"---->删除表失败：{msg}", 1)
        finally:
            # 重置线程停止事件
            self.stop_thread_event.clear()
            # 恢复UI操作
            self.ui.treeView.setEnabled(True)
            self.ui.tV_DataTable.setEnabled(True)

    def on_TreeClicked(self, index):
        """左键点击表：显示表信息（使用独立的数据库连接）"""
        if ShareInfo.sql_cfg == {}:
            ShareInfo.sql_cfg = ShareInfo.sql_cfg_default

        # 为每个点击创建独立的连接和游标，避免共享资源冲突
        db = ShareInfo.DBconnect()
        if not db:
            msg = "---->获取表信息失败：数据库连接失败"
            self.signal_Msg.emit(msg, 1)
            return

        cursor = db.cursor()
        tablename = index.data()
        sql = "select table_rows,data_length,create_time from information_schema.tables where table_name = %s"
        try:
            # 使用参数化查询，避免SQL注入
            cursor.execute(sql, (tablename,))
            res = cursor.fetchall()
            if res:
                self.ui.label_row.setText(str(res[0][0]))
                self.ui.label_length.setText(self.hum_convert(res[0][1]))
                self.ui.label_CreateDate.setText(str(res[0][2]))
            else:
                self.ui.label_row.setText("0")
                self.ui.label_length.setText("0B")
                self.ui.label_CreateDate.setText("未知")
        except Exception as e:
            print("---->SQL语句执行错误：{}".format(e))
            msg = "---->获取表信息错误：{}".format(e)
            self.signal_Msg.emit(msg, 1)
        finally:
            # 立即关闭连接和游标，释放资源
            cursor.close()
            db.close()

    def on_TreeDoubleClicked(self, index):
        """双击表：加载表数据（使用独立的数据库连接，避免共享资源）"""
        # 停止之前的线程
        self.stop_thread_event.set()
        if self.load_thread and self.load_thread.is_alive():
            self.load_thread.join(timeout=1)
        self.stop_thread_event.clear()

        tablename = index.data()
        # 为线程传递表名，在线程内部创建连接，避免跨线程使用连接
        self.load_thread = Thread(target=self.on_Thread_loadTables, args=(tablename,))
        self.load_thread.start()

    def on_Thread_loadTables(self, tablename):
        """线程中加载表数据（内部创建独立的数据库连接）"""
        if self.stop_thread_event.is_set():
            return

        # 线程内部创建独立的连接和游标，避免跨线程共享资源
        db = ShareInfo.DBconnect()
        if not db:
            self.signal_Msg.emit("---->加载表数据失败：数据库连接失败", 1)
            return

        cursor = db.cursor()
        sql = f"SELECT * FROM `{tablename}`"
        try:
            cursor.execute(sql)
            data = cursor.fetchall()
            des = cursor.description

            # 处理空表情况，避免列数不匹配
            header = [item[0] for item in des]
            if not data:
                df = pd.DataFrame(columns=header)
            else:
                df = pd.DataFrame(list(data), columns=header)

            # 检查是否需要停止更新
            if self.stop_thread_event.is_set():
                return

            # 发送信号到主线程更新UI
            self.signal_UpdateTable.emit(df)
        except Exception as e:
            print("---->SQL语句执行错误：{}".format(e))
            msg = "---->加载表数据错误：{}".format(e)
            self.signal_Msg.emit(msg, 1)
        finally:
            # 立即关闭连接和游标，释放资源
            cursor.close()
            db.close()

    def hum_convert(self, value):
        """字节单位转换"""
        if value is None or value == 0:
            return "0B"
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        size = 1024.0
        for i in range(len(units)):
            if (value / size) < 1:
                return "%.2f%s" % (value, units[i])
            value = value / size
        return "%.2f%s" % (value, units[-1])

    def on_SQLconnect(self):
        self._openSubWin("SqlConnect", Win_SQlconnect)

    def on_SQLupload(self):
        self._openSubWin("SqlUpload", Win_SQlupload)

    def on_SQLdownload(self):
        self._openSubWin("SqlDownload", Win_SQldownload)

    def _openSubWin(self, FuncClass, WinFuncClass):
        """打开MDI子窗口的内部函数"""
        def createSubWin():
            """创造子窗口的子函数"""
            subWindow = QMdiSubWindow()  # 创建子窗口对象
            # 加载UI到子窗口界面
            subWinFunc = WinFuncClass()
            subWindow.setWidget(subWinFunc)
            subWindow.setAttribute(Qt.WA_DeleteOnClose)  # 点击退出释放窗口
            # 把子窗口加入到MDI区域
            self.ui.mdiArea.addSubWindow(subWindow)
            # 存入表中，注意winFunc对象也要保存，不然对象没有引用，会销毁清除
            ShareInfo.subWinTable[str(FuncClass)] = {'subWindow': subWindow, 'subWinFunc': subWinFunc}
            print(ShareInfo.subWinTable)
            subWindow.show()  # 显示子窗口
            subWindow.setWindowState(Qt.WindowActive)
            subWindow.setWindowTitle('DataBase [{}]'.format(FuncClass))
            if FuncClass == "SqlConnect":
                subWindowFun = ShareInfo.subWinTable['SqlConnect']['subWinFunc']
                subWindowFun.getTables.connect(self.on_initTree)  # 连接mdi中子窗口的信号
                subWindowFun.msg_Signal.connect(self.on_Msg)
            if FuncClass == "SqlUpload":
                subWindowFun = ShareInfo.subWinTable['SqlUpload']['subWinFunc']
                subWindowFun.msg_Signal.connect(self.on_Msg)
            if FuncClass == "SqlDownload":
                subWindowFun = ShareInfo.subWinTable['SqlDownload']['subWinFunc']
                subWindowFun.msg_Signal.connect(self.on_Msg)
        # 如果该功能类型 实例不存在
        if str(FuncClass) not in ShareInfo.subWinTable:
            # 创建实例
            createSubWin()
            return
        # 如果该功能类型已经存在，直接显示出来
        subWindow = ShareInfo.subWinTable[str(FuncClass)]['subWindow']
        try:
            subWindow.show()
            subWindow.setWindowState(Qt.WindowActive)
        except:
            # show 异常原因肯定是用户手动关闭了该窗口，subWin对象已经不存在了
            createSubWin()

    def on_Msg(self, msg, cnt):
        """显示消息到文本框"""
        self.ui.tE_Msg.setTextColor(QtGui.QColor('black'))
        if cnt == 1:
            self.ui.tE_Msg.setTextColor(QtGui.QColor('red'))
        self.ui.tE_Msg.append(msg)

    def on_Console(self):
        """执行SQL控制台语句"""
        if ShareInfo.sql_cfg == {}:
            QMessageBox.critical(self, "错误", "未连接数据库！")
            msg = '---->未连接数据库！'
            self.signal_Msg.emit(msg, 1)
            return
        conn = ShareInfo.DBconnect()
        cur = conn.cursor()
        try:
            sql = self.ui.tE_Console.toPlainText()
            msg = "---->执行SQL语句：{}".format(sql)
            self.signal_Msg.emit(msg, 0)
            cur.execute(sql)
            data = cur.fetchall()
            if data:
                msg = '----> {}'.format(data)
                self.signal_Msg.emit(msg, 0)
            conn.commit()
        except Exception as e:
            msg = "---->SQL语句执行错误：{}".format(e)
            print(msg)
            self.signal_Msg.emit(msg, 1)
        finally:
            # 释放资源
            if cur:
                cur.close()
            if conn:
                conn.close()

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        """窗口关闭事件"""
        # 停止线程
        self.stop_thread_event.set()
        if self.load_thread and self.load_thread.is_alive():
            self.load_thread.join(timeout=1)

        self.closed.emit()
        a0.accept()


class pandasModel(QAbstractTableModel):
    """Pandas DataFrame适配QTableView的模型"""

    def __init__(self, data):
        QAbstractTableModel.__init__(self)
        self._data = data

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parnet=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid():
            if role == Qt.ItemDataRole.DisplayRole:
                return str(self._data.iloc[index.row(), index.column()])
        return None

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._data.columns[col]
        elif orientation == Qt.Vertical and role == Qt.ItemDataRole.DisplayRole:
            return col
        return None


class myThread(QThread):
    """测试线程类（修复初始化错误）"""
    loading = pyqtSignal()

    def __init__(self):
        super().__init__()

    def run(self) -> None:
        print("QThread RUN")