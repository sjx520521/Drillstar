import importlib

from PyQt5.QtCore import QFile, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QToolButton, QWidget

from dataanalysis.buttonNode import ButtonNode
from dataanalysis.share_DataAnalysis import ShareInfo
from dataanalysis.ui.dataAnalysis_ui import Ui_DataAnalysis
from nodeeditor.node_graphics_view import QDMGraphicsView
from nodeeditor.node_scene import Scene


class Win_DataAnalysis(QMainWindow):
    closed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.ui = Ui_DataAnalysis()
        self.ui.setupUi(self)
        self.initUI()

        self.stylesheet_filename = "style.qss"
        self.loadStylesheet(self.stylesheet_filename)
        self.ui.toolBox.setCurrentIndex(0)
        self.ui.toolBox.setStyleSheet(
            "QToolBox:tab{background: #FFFFFF;border-radius:2px;min-height:100px;font: normal normal 14px 'SimSun'}"
        )

        process_page = self.ui.toolBox.findChild(QWidget, "page_process")
        if process_page:
            process_page.setMinimumHeight(600)
            process_layout = process_page.layout()
            if process_layout:
                process_layout.setSpacing(10)
                process_layout.setContentsMargins(10, 10, 10, 10)

        self.ui.btn_Data_CSVimport.clicked.connect(self.on_clicked_CSVimport)
        self.ui.btn_Data_Excelimport.clicked.connect(self.on_clicked_Excelimpot)
        self.ui.btn_Data_SQLimport.clicked.connect(self.on_clicked_SQLimpot)
        self.ui.btn_Data_DataList.clicked.connect(self.on_clicked_DataTable)
        self.ui.btn_Data_Datainfo.clicked.connect(self.on_Clicked_DataInfo)
        self.ui.btn_Data_Save.clicked.connect(self.on_clicked_Save)

        self.ui.btn_Process_Clean.clicked.connect(self.on_Clicked_Process_Clean)
        self.ui.btn_Process_Filter.clicked.connect(self.on_Clicked_Process_Filter)
        self.ui.btn_Process_Time.clicked.connect(self.on_Clicked_Process_Time)
        self.ui.btn_Process_Frequency.clicked.connect(self.on_Clicked_Process_Frequency)
        self.ui.btn_Process_timeFrequency.clicked.connect(self.on_Clicked_Process_TimeFrequency)
        self.ui.btn_Process_Resample.clicked.connect(self.on_Clicked_Process_Resample)
        self.ui.btn_Process_Wavelet.clicked.connect(self.on_Clicked_Process_Wavelet)

        self.ui.btn_Model_PCA.clicked.connect(self.on_Clicked_Model_PCA)
        self.ui.btn_Model_SVM.clicked.connect(self.on_Clicked_Model_SVM)
        self.ui.btn_Model_KMeans.clicked.connect(self.on_Clicked_Model_KMeans)
        self.ui.btn_Model_NN.clicked.connect(self.on_Clicked_Model_NN)
        self.ui.btn_Model_Lstm.clicked.connect(self.on_Clicked_Model_LSTM)
        self.ui.btn_Model_NaiveBayes.clicked.connect(self.on_Clicked_Model_NB)
        self.ui.btn_Model_Informer.clicked.connect(self.on_Clicked_Model_Informer)
        self.ui.btn_Model_LinearRegression.clicked.connect(self.on_Clicked_Model_LinearRegression)
        self.ui.btn_Model_LogisticRegression.clicked.connect(self.on_Clicked_Model_LogisticRegression)
        self.ui.btn_Model_SaveModel.clicked.connect(self.on_Clicked_Model_SaveModel)
        self.ui.btn_Model_LoadModel.clicked.connect(self.on_Clicked_Model_LoadModel)
        self.ui.btn_Model_Predict.clicked.connect(self.on_Clicked_Model_Predict)

        self.ui.btn_Display_LinePlot.clicked.connect(self.on_Clicked_Display_LinerPlot)
        self.ui.btn_Display_ScatterPlot.clicked.connect(self.on_Clicked_Display_ScatterPlot)
        self.ui.btn_Display_BarPlot.clicked.connect(self.on_Clicked_Display_BarPlot)

        self.ui.btn_OilFunc_Standardization.clicked.connect(self.on_Clicked_OilFunc_Standardization)
        self.ui.btn_OilFunc_TimeConv.clicked.connect(self.on_Clicked_OilFunc_TimeConv)
        self.ui.btn_OilFunc_TimeDepth.clicked.connect(self.on_Clicked_OilFunc_TimeDepth)
        self.ui.btn_OilFunc_MSE.clicked.connect(self.on_Clicked_OilFunc_MSE)
        self.ui.btn_OilFunc_StickSlip.clicked.connect(self.on_Clicked_OilFunc_StickSlip)
        self.ui.btn_OilFunc_StuckPipe.clicked.connect(self.on_Clicked_OilFunc_StuckPipe)

    def initUI(self):
        self.sence = Scene()
        self.grScene = self.sence.grScene
        self.view = QDMGraphicsView(self.grScene, self)
        self.ui.verticalLayout_graph.addWidget(self.view)
        self._analysis_button_point_size = self.ui.btn_Data_Datainfo.font().pointSize()

        self._setup_button(self.ui.btn_Data_Excelimport, "icon/b_excel.png", "Excel导入")
        self._setup_button(self.ui.btn_Data_CSVimport, "icon/b_csvimport.png", "CSV导入")
        self._setup_button(self.ui.btn_Data_SQLimport, "icon/b_sql.png", "SQL")
        self._setup_button(self.ui.btn_Data_DataList, "icon/b_dataTable.png", "数据表")
        self._setup_button(self.ui.btn_Data_Datainfo, "icon/b_datainfo.png", "数据信息")
        self._setup_button(self.ui.btn_Data_Save, "icon/b_save.png", "保存数据")

        self._setup_button(self.ui.btn_Process_Clean, "icon/b_clean.png", "清洗")
        self._setup_button(self.ui.btn_Process_Filter, "icon/b_filter.png", "滤波")
        self._setup_button(self.ui.btn_Process_Time, "icon/b_time.png", "时域")
        self._setup_button(self.ui.btn_Process_Frequency, "icon/b_frequency.png", "频域")
        self._setup_button(self.ui.btn_Process_timeFrequency, "icon/b_timeFrequency.png", "时频域")
        self._setup_button(self.ui.btn_Process_Resample, "icon/b_resample.png", "重采样")
        self._setup_button(self.ui.btn_Process_Wavelet, "icon/b_wavelet.png", "小波分析")

        self._setup_button(self.ui.btn_Model_PCA, "icon/b_pca.png", "PCA")
        self._setup_button(self.ui.btn_Model_SVM, "icon/b_svm.png", "SVM")
        self._setup_button(self.ui.btn_Model_KMeans, "icon/b_KMeans.png", "K-Means")
        self._setup_button(self.ui.btn_Model_NN, "icon/b_nn.png", "Neural Net", "Neural Network")
        self._setup_button(self.ui.btn_Model_Lstm, "icon/b_lstm.png", "Lstm")
        self._setup_button(self.ui.btn_Model_NaiveBayes, "icon/b_bn.png", "NaiveBayes")
        self._setup_button(self.ui.btn_Model_Informer, "icon/b_informer.png", "Informer")
        self._setup_button(self.ui.btn_Model_LinearRegression, "icon/b_lr.png", "Linear Reg", "Linear Regression")
        self._setup_button(self.ui.btn_Model_LogisticRegression, "icon/b_lcr.png", "Logistic Reg", "Logistic Regression")
        self._setup_button(self.ui.btn_Model_SaveModel, "icon/b_savemodel.png", "SaveModel")
        self._setup_button(self.ui.btn_Model_LoadModel, "icon/b_loadmodel.png", "LoadModel")
        self.ui.btn_Model_Predict = QToolButton(self.ui.widget_3)
        self.ui.btn_Model_Predict.setMinimumSize(self.ui.btn_Model_LoadModel.minimumSize())
        self.ui.btn_Model_Predict.setMaximumSize(self.ui.btn_Model_LoadModel.maximumSize())
        self.ui.btn_Model_Predict.setFont(self.ui.btn_Model_LoadModel.font())
        self.ui.btn_Model_Predict.setObjectName("btn_Model_Predict")
        self.ui.gridLayout_3.addWidget(self.ui.btn_Model_Predict, 3, 2, 1, 1)
        self._setup_button(self.ui.btn_Model_Predict, "icon/b_show.png", "模型应用")
        self._arrange_model_buttons()

        self._setup_button(self.ui.btn_Display_LinePlot, "icon/b_lp.png", "Liner Plot")
        self._setup_button(self.ui.btn_Display_ScatterPlot, "icon/b_sp.png", "Scatter Plot")
        self._setup_button(self.ui.btn_Display_BarPlot, "icon/b_bp.png", "Bar Plot")

        self._setup_button(self.ui.btn_OilFunc_Standardization, "icon/b_standardization.png", "工程值转换")
        self._setup_button(self.ui.btn_OilFunc_TimeConv, "icon/b_timeconv.png", "时间转换")
        self._setup_button(self.ui.btn_OilFunc_TimeDepth, "icon/b_timedepth.png", "时深对标")
        self._setup_button(self.ui.btn_OilFunc_MSE, "icon/b_MSE.png", "MSE")
        self._setup_button(self.ui.btn_OilFunc_StickSlip, "icon/b_stickslip.png", "粘滑分析")
        self._setup_button(self.ui.btn_OilFunc_StuckPipe, "icon/b_stuckpipe.png", "卡钻分析")

    def _setup_button(self, btn, icon_path, text, tooltip=None):
        btn.setFont(self._button_font_for_text(text))
        btn.setIcon(QIcon(icon_path))
        btn.setText(text)
        btn.setToolTip(tooltip or text)
        btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        btn.setIconSize(QSize(50, 50))

    def _button_font_for_text(self, text):
        family = "Times New Roman" if any(char.isascii() and char.isalpha() for char in text) else "微软雅黑"
        return QFont(family, self._analysis_button_point_size)

    def _arrange_model_buttons(self):
        layout = self.ui.gridLayout_3
        layout.addWidget(self.ui.btn_Model_PCA, 0, 0, 1, 1)
        layout.addWidget(self.ui.btn_Model_SVM, 0, 1, 1, 1)
        layout.addWidget(self.ui.btn_Model_KMeans, 0, 2, 1, 1)
        layout.addWidget(self.ui.btn_Model_NaiveBayes, 1, 0, 1, 1)
        layout.addWidget(self.ui.btn_Model_LogisticRegression, 1, 1, 1, 1)
        layout.addWidget(self.ui.btn_Model_LinearRegression, 1, 2, 1, 1)
        layout.addWidget(self.ui.btn_Model_NN, 2, 0, 1, 1)
        layout.addWidget(self.ui.btn_Model_Lstm, 2, 1, 1, 1)
        layout.addWidget(self.ui.btn_Model_Informer, 2, 2, 1, 1)
        layout.addWidget(self.ui.btn_Model_SaveModel, 3, 0, 1, 1)
        layout.addWidget(self.ui.btn_Model_LoadModel, 3, 1, 1, 1)
        layout.addWidget(self.ui.btn_Model_Predict, 3, 2, 1, 1)

    def loadStylesheet(self, filename):
        print("STYLE loading", filename)
        file = QFile(filename)
        file.open(QFile.ReadOnly | QFile.Text)
        stylesheet = file.readAll()
        self.setStyleSheet(str(stylesheet, encoding="utf-8"))

    def _module_window(self, module_name, class_name):
        def factory(node):
            module = importlib.import_module(module_name)
            window_class = getattr(module, class_name)
            return window_class(node)

        return factory

    def _placeholder_window(self, title):
        def factory(_node):
            window = QWidget()
            window.setWindowTitle(title)
            return window

        return factory

    def on_clicked_CSVimport(self):
        self._create_node(
            "icon/csv.png",
            "node_Data_CSV",
            "CSV",
            [],
            [1],
            self._module_window("dataanalysis.data.csvImport", "Win_CSVImport"),
        )

    def on_clicked_Excelimpot(self):
        self._create_node(
            "icon/excel.png",
            "node_Data_Excel",
            "Excel",
            [],
            [1],
            self._module_window("dataanalysis.data.excelimport", "Win_ExcelImport"),
        )

    def on_clicked_SQLimpot(self):
        self._create_node(
            "icon/database.png",
            "node_Data_SQL",
            "SQL",
            [],
            [1],
            self._module_window("dataanalysis.data.sqlImport", "Win_SQLimport"),
        )

    def on_clicked_DataTable(self):
        self._create_node(
            "icon/datatable.png",
            "node_Data_DataTable",
            "数据表",
            [3],
            [1],
            self._module_window("dataanalysis.data.datatable", "Win_DataTable"),
        )

    def on_Clicked_DataInfo(self):
        self._create_node(
            "icon/datainfo.png",
            "node_Data_DataInfo",
            "数据信息",
            [3],
            [],
            self._module_window("dataanalysis.data.datdinfo", "Win_DataInfo"),
        )

    def on_clicked_Save(self):
        self._create_node(
            "icon/datasave.png",
            "node_Data_DataInfo",
            "Save",
            [3],
            [],
            self._module_window("dataanalysis.data.savedata", "Win_SaveData"),
        )

    def on_Clicked_Process_Clean(self):
        self._create_node(
            "icon/clean.png",
            "node_Process_Clean",
            "数据清洗",
            [3],
            [1],
            self._module_window("dataanalysis.process.clean", "Win_ProcessClean"),
        )

    def on_Clicked_Process_Filter(self):
        self._create_node(
            "icon/Filter.png",
            "node_Process_Filter",
            "滤波",
            [3],
            [1],
            self._module_window("dataanalysis.process.filter", "Win_ProcessFilter"),
        )

    def on_Clicked_Process_Time(self):
        self._create_node(
            "icon/time.png",
            "node_Process_Time",
            "时域",
            [3],
            [1],
            self._module_window("dataanalysis.process.time", "Win_ProcessTime"),
        )

    def on_Clicked_Process_Frequency(self):
        self._create_node(
            "icon/frequency.png",
            "node_Process_Frequency",
            "频域",
            [3],
            [],
            self._module_window("dataanalysis.process.frequency", "Win_ProcessFrequency"),
        )

    def on_Clicked_Process_TimeFrequency(self):
        self._create_node(
            "icon/timeFrequency.png",
            "node_Process_TimeFrequency",
            "时频域",
            [3],
            [],
            self._module_window("dataanalysis.process.timeFrequency", "Win_ProcessTimeFrequency"),
        )

    def on_Clicked_Process_Resample(self):
        self._create_node(
            "icon/resample.png",
            "node_Process_Resample",
            "重采样",
            [3, 3],
            [1],
            self._module_window("dataanalysis.process.resample", "Win_ProcessResample"),
        )

    def on_Clicked_Process_Wavelet(self):
        self._create_node(
            "icon/wavelet.png",
            "node_Process_Wavelet",
            "小波变换",
            [3],
            [1],
            self._module_window("dataanalysis.process.wavelet", "Win_ProcessWavelet"),
        )

    def on_Clicked_Model_PCA(self):
        self._create_node(
            "icon/n_pca.png",
            "node_Moedl_PCA",
            "PCA",
            [3],
            [1],
            self._module_window("dataanalysis.model.pca", "Win_ModelPCA"),
        )

    def on_Clicked_Model_SVM(self):
        self._create_node(
            "icon/n_svm.png",
            "node_Moedl_SVM",
            "SVM",
            [3],
            [1],
            self._module_window("dataanalysis.model.svm", "Win_ModelSVM"),
        )

    def on_Clicked_Model_KMeans(self):
        self._create_node(
            "icon/n_KMeans.png",
            "node_Moedl_KMeans",
            "K-Means",
            [3],
            [1],
            self._module_window("dataanalysis.model.kMeans", "Win_ModelKmeans"),
        )

    def on_Clicked_Model_NN(self):
        self._create_node(
            "icon/n_nn.png", "node_Moedl_NN", "NeuralNetwork", [3], [1],
            self._module_window("dataanalysis.model.NeuralNetwork", "Win_ModelNeuralNetwork"),
        )

    def on_Clicked_Model_LSTM(self):
        self._create_node(
            "icon/n_lstm.png", "node_Moedl_Lstm", "Lstm", [3], [1],
            self._module_window("dataanalysis.model.lstm", "Win_ModelLSTM"),
        )

    def on_Clicked_Model_NB(self):
        self._create_node(
            "icon/n_bn.png", "node_Moedl_NaiveBayes", "NaiveBayes", [3], [1],
            self._module_window("dataanalysis.model.NaiveBayes", "Win_ModelNaiveBayes"),
        )

    def on_Clicked_Model_Informer(self):
        self._create_node(
            "icon/n_informer.png", "node_Moedl_Informer", "Informer", [3], [1, 2],
            self._module_window("dataanalysis.model.Informer", "Win_ModelInformer"),
        )

    def on_Clicked_Model_LinearRegression(self):
        self._create_node(
            "icon/n_lr.png",
            "node_Moedl_LinearRegression",
            "LinearRegressions",
            [3],
            [1],
            self._module_window("dataanalysis.model.LinearRegression", "Win_ModelLinearRegression"),
        )

    def on_Clicked_Model_LogisticRegression(self):
        self._create_node(
            "icon/n_lcr.png",
            "node_Moedl_LogisticRegression",
            "LogisticRegression",
            [3],
            [1],
            self._module_window("dataanalysis.model.LogisticRegression", "Win_ModelLogisticRegression"),
        )

    def on_Clicked_Model_SaveModel(self):
        self._create_node(
            "icon/n_savemodel.png",
            "node_Moedl_SaveModel",
            "SaveModel",
            [4],
            [],
            self._module_window("dataanalysis.model.saveModel", "Win_SaveModel"),
        )

    def on_Clicked_Model_LoadModel(self):
        self._create_node(
            "icon/n_loadmodel.png",
            "node_Moedl_LoadModel",
            "LoadModel",
            [],
            [4],
            self._module_window("dataanalysis.model.loadModel", "Win_LoadModel"),
        )

    def on_Clicked_Model_Predict(self):
        self._create_node(
            "icon/n_show.png",
            "node_Moedl_Predict",
            "模型应用",
            [4, 3],
            [1],
            self._module_window("dataanalysis.model.predictModel", "Win_ModelPredict"),
        )

    def on_Clicked_Display_LinerPlot(self):
        self._create_node(
            "icon/b_lp.png",
            "node_Moedl_LinerPlot",
            "Liner Plot",
            [1],
            [],
            self._module_window("dataanalysis.display.LinePlot", "Win_DisplayLinePlot"),
        )

    def on_Clicked_Display_ScatterPlot(self):
        self._create_node(
            "icon/b_sp.png",
            "node_Moedl_ScatterPlot",
            "Scatter Plot",
            [1],
            [],
            self._module_window("dataanalysis.display.ScatterPlot", "Win_DisplayScatterPlot"),
        )

    def on_Clicked_Display_BarPlot(self):
        self._create_node(
            "icon/b_bp.png",
            "node_Moedl_BarPlot",
            "Bar Plot",
            [1],
            [],
            self._module_window("dataanalysis.display.BarPlot", "Win_DisplayBarPlot"),
        )

    def on_Clicked_OilFunc_Standardization(self):
        self._create_node(
            "icon/Standardization.png",
            "node_OilFunc_Standardization",
            "工程值转换",
            [3],
            [1],
            self._module_window("dataanalysis.oilFunc.Standardization", "Win_Standardization"),
        )

    def on_Clicked_OilFunc_TimeDepth(self):
        self._create_node(
            "icon/n_timedepth.png",
            "node_OilFunc_TimeDepth",
            "时深对标",
            [3],
            [1],
            self._module_window("dataanalysis.oilFunc.TimeDepth", "Win_OilFuncTimeDepth"),
        )

    def on_Clicked_OilFunc_StuckPipe(self):
        self._create_node(
            "icon/stuckpipe.png",
            "node_OilFunc_Stuckpipe",
            "卡钻分析",
            [3],
            [1],
            self._module_window("dataanalysis.oilFunc.StuckPipe", "Win_OilFuncStuckPipe"),
        )

    def on_Clicked_OilFunc_MSE(self):
        self._create_node(
            "icon/MSE.png",
            "node_OilFunc_MSE",
            "MSE",
            [3],
            [1],
            self._module_window("dataanalysis.oilFunc.MSE", "Win_OilFuncMSE"),
        )

    def on_Clicked_OilFunc_StickSlip(self):
        self._create_node(
            "icon/stickslip.png",
            "node_OilFunc_Stickslip",
            "粘滑分析",
            [3],
            [],
            self._module_window("dataanalysis.oilFunc.StickSlip", "Win_OilFuncStickSlip"),
        )

    def on_Clicked_OilFunc_TimeConv(self):
        self._create_node(
            "icon/timeconv.png",
            "node_oilFunc.TimeConv",
            "时间转换",
            [3],
            [1],
            self._module_window("dataanalysis.oilFunc.TimeConv", "Win_OilFuncTimeConv"),
        )

    def _create_node(self, icon, obj_name, title, inputs, outputs, window):
        try:
            btn_node = ButtonNode(self.sence, title, inputs=inputs, outputs=outputs, window=window)
            btn_node.icon = icon
            btn_node.content_label_objname = obj_name
            btn_node.content.update_icon()
            btn_node.grNode.update()
            self.sence.addNode(btn_node)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建节点失败：{e}")

    def closeEvent(self, a0):
        ShareInfo.app.closeAllWindows()
        self.closed.emit()
        a0.accept()


_orig_data_analysis_initUI = Win_DataAnalysis.initUI
_orig_on_clicked_oilfunc_stickslip = Win_DataAnalysis.on_Clicked_OilFunc_StickSlip


def _data_analysis_initUI_paste_slip(self):
    _orig_data_analysis_initUI(self)
    self.ui.btn_OilFunc_StickSlip.setText("粘滑分析")


def _data_analysis_on_clicked_oilfunc_stickslip(self):
    self._create_node(
        "icon/stickslip.png",
        "node_OilFunc_Stickslip",
        "粘滑分析",
        [3],
        [1],
        self._module_window("dataanalysis.oilFunc.StickSlip", "Win_OilFuncStickSlip"),
    )


Win_DataAnalysis.initUI = _data_analysis_initUI_paste_slip
Win_DataAnalysis.on_Clicked_OilFunc_StickSlip = _data_analysis_on_clicked_oilfunc_stickslip
