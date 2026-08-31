import os
import sys
from pathlib import Path


def _get_app_base_dir():
    """Resolve the runtime base directory for both source and packaged runs."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


APP_BASE_DIR = _get_app_base_dir()
os.chdir(APP_BASE_DIR)
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtWidgets import QMessageBox
from PyQt5 import QtCore
from PyQt5.QtCore import Qt

from ui.main_ui import Ui_main

from dataanalysis.share_DataAnalysis import ShareInfo
from loading import LoadingProgress


class Win_Main(QWidget):

    def __init__(self):
        super().__init__()  #继承
        self.ui = Ui_main()  #实例化
        self.ui.setupUi(self)  #初始化
        self.win_datascope = None
        self.win_database = None
        self.win_dataanalysis = None
        self.ui.btn_simulation_experiment.clicked.connect(self.on_SimulationExperiment_Click)
        self.ui.btn_data_management.clicked.connect(self.on_DataManagement_Click)
        self.ui.btn_data_analysis.clicked.connect(self.on_DataAnalysis)

        self.loading = LoadingProgress()

    def on_SimulationExperiment_Click(self):
        try:
            from datascope.datascope_main import Win_DataScope
            self.win_datascope = Win_DataScope()
            self.win_datascope.closed.connect(self.show)
            self.win_datascope.show()
            self.hide()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"模拟实验模块打开失败：{e}")
        return

    def on_DataManagement_Click(self):
        from database.database_main import Win_DataBase
        self.win_database = Win_DataBase()
        self.win_database.closed.connect(self.show)
        self.win_database.show()
        self.hide()
        return

    def on_DataAnalysis(self):
        from dataanalysis.dataAnalysis_main import Win_DataAnalysis
        self.win_dataanalysis = Win_DataAnalysis()
        self.win_dataanalysis.closed.connect(self.show)
        self.win_dataanalysis.show()
        self.hide()
        return

    def on_loading(self):
        print("emit")
        self.loading.show()


if __name__ == "__main__":

    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_EnableHighDpiScaling)  #调整不同屏幕对控件大小得影响

    # create the application and the main window
    app = QApplication(sys.argv)
    window = Win_Main()

    ShareInfo.app = app

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)  #显示高清图像
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    # setup stylesheet
    # apply_stylesheet(app, theme='dark_teal.xml')
    # setup stylesheet
    # app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    # or in new API
    # app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt5'))
    # setup stylesheet
    # app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt5', palette=LightPalette()))
    # app.setStyle('Fusion')
    # run
    window.show()

    sys.exit(app.exec_())  # 监视进程直至退出
