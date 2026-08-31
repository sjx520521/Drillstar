# -*- coding: utf-8 -*-

from PyQt5 import QtCore, QtWidgets


class Ui_OilFuncStuckPipe(object):
    def setupUi(self, OilFuncStuckPipe):
        OilFuncStuckPipe.setObjectName("OilFuncStuckPipe")
        OilFuncStuckPipe.resize(980, 720)
        OilFuncStuckPipe.setMinimumSize(QtCore.QSize(760, 560))

        self.verticalLayout_root = QtWidgets.QVBoxLayout(OilFuncStuckPipe)
        self.verticalLayout_root.setObjectName("verticalLayout_root")
        self.verticalLayout_root.setSpacing(10)
        self.verticalLayout_root.setContentsMargins(12, 12, 12, 12)

        self.splitter_main = QtWidgets.QSplitter(OilFuncStuckPipe)
        self.splitter_main.setOrientation(QtCore.Qt.Horizontal)
        self.splitter_main.setObjectName("splitter_main")

        self.widget_left = QtWidgets.QWidget(self.splitter_main)
        self.widget_left.setObjectName("widget_left")
        self.verticalLayout_left = QtWidgets.QVBoxLayout(self.widget_left)
        self.verticalLayout_left.setObjectName("verticalLayout_left")
        self.verticalLayout_left.setSpacing(10)
        self.verticalLayout_left.setContentsMargins(0, 0, 0, 0)

        self.groupBox = QtWidgets.QGroupBox(self.widget_left)
        self.groupBox.setObjectName("groupBox")
        self.formLayout = QtWidgets.QFormLayout(self.groupBox)
        self.formLayout.setObjectName("formLayout")

        self.label_Time = QtWidgets.QLabel(self.groupBox)
        self.label_Time.setObjectName("label_Time")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.label_Time)
        self.cB_Time = QtWidgets.QComboBox(self.groupBox)
        self.cB_Time.setObjectName("cB_Time")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.FieldRole, self.cB_Time)

        self.label_WOB = QtWidgets.QLabel(self.groupBox)
        self.label_WOB.setObjectName("label_WOB")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.LabelRole, self.label_WOB)
        self.cB_WOB = QtWidgets.QComboBox(self.groupBox)
        self.cB_WOB.setObjectName("cB_WOB")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.FieldRole, self.cB_WOB)

        self.label_Torque = QtWidgets.QLabel(self.groupBox)
        self.label_Torque.setObjectName("label_Torque")
        self.formLayout.setWidget(2, QtWidgets.QFormLayout.LabelRole, self.label_Torque)
        self.cB_Torque = QtWidgets.QComboBox(self.groupBox)
        self.cB_Torque.setObjectName("cB_Torque")
        self.formLayout.setWidget(2, QtWidgets.QFormLayout.FieldRole, self.cB_Torque)

        self.label_RPM = QtWidgets.QLabel(self.groupBox)
        self.label_RPM.setObjectName("label_RPM")
        self.formLayout.setWidget(3, QtWidgets.QFormLayout.LabelRole, self.label_RPM)
        self.cB_RPM = QtWidgets.QComboBox(self.groupBox)
        self.cB_RPM.setObjectName("cB_RPM")
        self.formLayout.setWidget(3, QtWidgets.QFormLayout.FieldRole, self.cB_RPM)

        self.verticalLayout_left.addWidget(self.groupBox)

        self.groupBox_2 = QtWidgets.QGroupBox(self.widget_left)
        self.groupBox_2.setObjectName("groupBox_2")
        self.verticalLayout_standard = QtWidgets.QVBoxLayout(self.groupBox_2)
        self.verticalLayout_standard.setObjectName("verticalLayout_standard")
        self.verticalLayout_standard.setContentsMargins(10, 10, 10, 10)

        self.label_standard = QtWidgets.QLabel(self.groupBox_2)
        self.label_standard.setText("")
        self.label_standard.setWordWrap(True)
        self.label_standard.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.label_standard.setObjectName("label_standard")
        self.verticalLayout_standard.addWidget(self.label_standard)

        self.verticalLayout_left.addWidget(self.groupBox_2)
        self.verticalLayout_left.addStretch(1)

        self.widget_right = QtWidgets.QWidget(self.splitter_main)
        self.widget_right.setObjectName("widget_right")
        self.verticalLayout_right = QtWidgets.QVBoxLayout(self.widget_right)
        self.verticalLayout_right.setObjectName("verticalLayout_right")
        self.verticalLayout_right.setSpacing(10)
        self.verticalLayout_right.setContentsMargins(0, 0, 0, 0)

        self.label_summary = QtWidgets.QLabel(self.widget_right)
        self.label_summary.setWordWrap(True)
        self.label_summary.setObjectName("label_summary")
        self.verticalLayout_right.addWidget(self.label_summary)

        self.widget_plot = QtWidgets.QWidget(self.widget_right)
        self.widget_plot.setObjectName("widget_plot")
        self.widget_plot.setMinimumHeight(420)
        self.verticalLayout_right.addWidget(self.widget_plot)

        self.splitter_main.setStretchFactor(0, 0)
        self.splitter_main.setStretchFactor(1, 1)
        self.verticalLayout_root.addWidget(self.splitter_main)

        self.horizontalLayout_btn = QtWidgets.QHBoxLayout()
        self.horizontalLayout_btn.setObjectName("horizontalLayout_btn")

        self.btn_Load = QtWidgets.QPushButton(OilFuncStuckPipe)
        self.btn_Load.setObjectName("btn_Load")
        self.btn_Load.setMinimumHeight(32)
        self.horizontalLayout_btn.addWidget(self.btn_Load)

        spacer_item = QtWidgets.QSpacerItem(
            40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum
        )
        self.horizontalLayout_btn.addItem(spacer_item)

        self.btn_apply = QtWidgets.QPushButton(OilFuncStuckPipe)
        self.btn_apply.setObjectName("btn_apply")
        self.btn_apply.setMinimumHeight(32)
        self.horizontalLayout_btn.addWidget(self.btn_apply)

        self.btn_Transfer = QtWidgets.QPushButton(OilFuncStuckPipe)
        self.btn_Transfer.setObjectName("btn_Transfer")
        self.btn_Transfer.setMinimumHeight(32)
        self.horizontalLayout_btn.addWidget(self.btn_Transfer)

        self.verticalLayout_root.addLayout(self.horizontalLayout_btn)

        self.retranslateUi(OilFuncStuckPipe)
        QtCore.QMetaObject.connectSlotsByName(OilFuncStuckPipe)

    def retranslateUi(self, OilFuncStuckPipe):
        _translate = QtCore.QCoreApplication.translate
        OilFuncStuckPipe.setWindowTitle(_translate("OilFuncStuckPipe", "卡钻分析"))
        self.groupBox.setTitle(_translate("OilFuncStuckPipe", "现场信号"))
        self.label_Time.setText(_translate("OilFuncStuckPipe", "时间列"))
        self.label_WOB.setText(_translate("OilFuncStuckPipe", "钻压列"))
        self.label_Torque.setText(_translate("OilFuncStuckPipe", "扭矩列"))
        self.label_RPM.setText(_translate("OilFuncStuckPipe", "转速列"))
        self.groupBox_2.setTitle(_translate("OilFuncStuckPipe", "现场判读说明"))
        self.label_summary.setText(_translate("OilFuncStuckPipe", "当前状态：未加载数据。"))
        self.btn_Load.setText(_translate("OilFuncStuckPipe", "Load"))
        self.btn_apply.setText(_translate("OilFuncStuckPipe", "Calculate"))
        self.btn_Transfer.setText(_translate("OilFuncStuckPipe", "Transfer"))
