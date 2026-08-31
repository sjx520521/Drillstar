# -*- coding: utf-8 -*-

from PyQt5 import QtCore, QtWidgets


class Ui_OilFuncMSE(object):
    def setupUi(self, OilFuncMSE):
        OilFuncMSE.setObjectName("OilFuncMSE")
        OilFuncMSE.resize(960, 720)

        self.verticalLayout_2 = QtWidgets.QVBoxLayout(OilFuncMSE)
        self.verticalLayout_2.setObjectName("verticalLayout_2")

        self.label_Math = QtWidgets.QLabel(OilFuncMSE)
        self.label_Math.setText("")
        self.label_Math.setAlignment(QtCore.Qt.AlignCenter)
        self.label_Math.setWordWrap(True)
        self.label_Math.setObjectName("label_Math")
        self.verticalLayout_2.addWidget(self.label_Math)

        self.groupBox_config = QtWidgets.QGroupBox(OilFuncMSE)
        self.groupBox_config.setObjectName("groupBox_config")
        self.verticalLayout_config = QtWidgets.QVBoxLayout(self.groupBox_config)
        self.verticalLayout_config.setObjectName("verticalLayout_config")

        self.formLayout = QtWidgets.QFormLayout()
        self.formLayout.setObjectName("formLayout")

        self.label_WOB = QtWidgets.QLabel(self.groupBox_config)
        self.label_WOB.setObjectName("label_WOB")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.label_WOB)
        self.cB_WOB = QtWidgets.QComboBox(self.groupBox_config)
        self.cB_WOB.setObjectName("cB_WOB")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.FieldRole, self.cB_WOB)

        self.label_TOQ = QtWidgets.QLabel(self.groupBox_config)
        self.label_TOQ.setObjectName("label_TOQ")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.LabelRole, self.label_TOQ)
        self.cB_TOQ = QtWidgets.QComboBox(self.groupBox_config)
        self.cB_TOQ.setObjectName("cB_TOQ")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.FieldRole, self.cB_TOQ)

        self.label_RPM = QtWidgets.QLabel(self.groupBox_config)
        self.label_RPM.setObjectName("label_RPM")
        self.formLayout.setWidget(2, QtWidgets.QFormLayout.LabelRole, self.label_RPM)
        self.cB_RPM = QtWidgets.QComboBox(self.groupBox_config)
        self.cB_RPM.setObjectName("cB_RPM")
        self.formLayout.setWidget(2, QtWidgets.QFormLayout.FieldRole, self.cB_RPM)

        self.label_RateMode = QtWidgets.QLabel(self.groupBox_config)
        self.label_RateMode.setObjectName("label_RateMode")
        self.formLayout.setWidget(3, QtWidgets.QFormLayout.LabelRole, self.label_RateMode)
        self.cB_RateMode = QtWidgets.QComboBox(self.groupBox_config)
        self.cB_RateMode.setObjectName("cB_RateMode")
        self.formLayout.setWidget(3, QtWidgets.QFormLayout.FieldRole, self.cB_RateMode)

        self.label_RateColumn = QtWidgets.QLabel(self.groupBox_config)
        self.label_RateColumn.setObjectName("label_RateColumn")
        self.formLayout.setWidget(4, QtWidgets.QFormLayout.LabelRole, self.label_RateColumn)
        self.cB_RateColumn = QtWidgets.QComboBox(self.groupBox_config)
        self.cB_RateColumn.setObjectName("cB_RateColumn")
        self.formLayout.setWidget(4, QtWidgets.QFormLayout.FieldRole, self.cB_RateColumn)

        self.label_TimeColumn = QtWidgets.QLabel(self.groupBox_config)
        self.label_TimeColumn.setObjectName("label_TimeColumn")
        self.formLayout.setWidget(5, QtWidgets.QFormLayout.LabelRole, self.label_TimeColumn)
        self.cB_TimeColumn = QtWidgets.QComboBox(self.groupBox_config)
        self.cB_TimeColumn.setObjectName("cB_TimeColumn")
        self.formLayout.setWidget(5, QtWidgets.QFormLayout.FieldRole, self.cB_TimeColumn)

        self.label_DepthColumn = QtWidgets.QLabel(self.groupBox_config)
        self.label_DepthColumn.setObjectName("label_DepthColumn")
        self.formLayout.setWidget(6, QtWidgets.QFormLayout.LabelRole, self.label_DepthColumn)
        self.cB_DepthColumn = QtWidgets.QComboBox(self.groupBox_config)
        self.cB_DepthColumn.setObjectName("cB_DepthColumn")
        self.formLayout.setWidget(6, QtWidgets.QFormLayout.FieldRole, self.cB_DepthColumn)

        self.label_BitDiameter = QtWidgets.QLabel(self.groupBox_config)
        self.label_BitDiameter.setObjectName("label_BitDiameter")
        self.formLayout.setWidget(7, QtWidgets.QFormLayout.LabelRole, self.label_BitDiameter)
        self.le_BitDiameter = QtWidgets.QLineEdit(self.groupBox_config)
        self.le_BitDiameter.setObjectName("le_BitDiameter")
        self.formLayout.setWidget(7, QtWidgets.QFormLayout.FieldRole, self.le_BitDiameter)

        self.verticalLayout_config.addLayout(self.formLayout)

        self.label_RateHint = QtWidgets.QLabel(self.groupBox_config)
        self.label_RateHint.setWordWrap(True)
        self.label_RateHint.setObjectName("label_RateHint")
        self.verticalLayout_config.addWidget(self.label_RateHint)

        self.verticalLayout_2.addWidget(self.groupBox_config)

        self.horizontalLayout_func = QtWidgets.QHBoxLayout()
        self.horizontalLayout_func.setObjectName("horizontalLayout_func")
        self.btn_Load = QtWidgets.QPushButton(OilFuncMSE)
        self.btn_Load.setObjectName("btn_Load")
        self.horizontalLayout_func.addWidget(self.btn_Load)
        self.btn_Calculate = QtWidgets.QPushButton(OilFuncMSE)
        self.btn_Calculate.setObjectName("btn_Calculate")
        self.horizontalLayout_func.addWidget(self.btn_Calculate)
        self.btn_Transfer = QtWidgets.QPushButton(OilFuncMSE)
        self.btn_Transfer.setObjectName("btn_Transfer")
        self.horizontalLayout_func.addWidget(self.btn_Transfer)

        spacer_item = QtWidgets.QSpacerItem(
            40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum
        )
        self.horizontalLayout_func.addItem(spacer_item)

        self.btn_Clear = QtWidgets.QPushButton(OilFuncMSE)
        self.btn_Clear.setObjectName("btn_Clear")
        self.horizontalLayout_func.addWidget(self.btn_Clear)
        self.verticalLayout_2.addLayout(self.horizontalLayout_func)

        self.label_Summary = QtWidgets.QLabel(OilFuncMSE)
        self.label_Summary.setWordWrap(True)
        self.label_Summary.setObjectName("label_Summary")
        self.verticalLayout_2.addWidget(self.label_Summary)

        self.scrollArea = QtWidgets.QScrollArea(OilFuncMSE)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setObjectName("scrollArea")
        self.scrollAreaWidgetContents = QtWidgets.QWidget()
        self.scrollAreaWidgetContents.setGeometry(QtCore.QRect(0, 0, 940, 360))
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")
        self.verticalLayout_plot = QtWidgets.QVBoxLayout(self.scrollAreaWidgetContents)
        self.verticalLayout_plot.setObjectName("verticalLayout_plot")
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)
        self.verticalLayout_2.addWidget(self.scrollArea)

        self.retranslateUi(OilFuncMSE)
        QtCore.QMetaObject.connectSlotsByName(OilFuncMSE)

    def retranslateUi(self, OilFuncMSE):
        _translate = QtCore.QCoreApplication.translate
        OilFuncMSE.setWindowTitle(_translate("OilFuncMSE", "MSE计算"))
        self.groupBox_config.setTitle(_translate("OilFuncMSE", "参数配置"))
        self.label_WOB.setText(_translate("OilFuncMSE", "WOB列"))
        self.label_TOQ.setText(_translate("OilFuncMSE", "TOQ列"))
        self.label_RPM.setText(_translate("OilFuncMSE", "RPM列"))
        self.label_RateMode.setText(_translate("OilFuncMSE", "ROP来源"))
        self.label_RateColumn.setText(_translate("OilFuncMSE", "ROP/钻时列"))
        self.label_TimeColumn.setText(_translate("OilFuncMSE", "时间列"))
        self.label_DepthColumn.setText(_translate("OilFuncMSE", "深度列"))
        self.label_BitDiameter.setText(_translate("OilFuncMSE", "钻头直径(mm)"))
        self.le_BitDiameter.setPlaceholderText(_translate("OilFuncMSE", "例如：215.9"))
        self.label_RateHint.setText(
            _translate("OilFuncMSE", "支持直接使用ROP、由钻时换算ROP、由时间和深度反算ROP。")
        )
        self.btn_Load.setText(_translate("OilFuncMSE", "Load"))
        self.btn_Calculate.setText(_translate("OilFuncMSE", "Calculate"))
        self.btn_Transfer.setText(_translate("OilFuncMSE", "Transfer"))
        self.btn_Clear.setText(_translate("OilFuncMSE", "清空图像"))
        self.label_Summary.setText(_translate("OilFuncMSE", "当前状态：未加载数据。"))
