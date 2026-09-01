# -*- coding: utf-8 -*-

from PyQt5 import QtCore, QtWidgets


class Ui_OilFuncStickSlip(object):
    def setupUi(self, OilFuncStickSlip):
        OilFuncStickSlip.setObjectName("OilFuncStickSlip")
        OilFuncStickSlip.resize(800, 700)
        OilFuncStickSlip.setMinimumSize(QtCore.QSize(600, 500))

        self.verticalLayout_3 = QtWidgets.QVBoxLayout(OilFuncStickSlip)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.verticalLayout_3.setSpacing(10)
        self.verticalLayout_3.setContentsMargins(10, 10, 10, 10)

        self.groupBox = QtWidgets.QGroupBox(OilFuncStickSlip)
        self.groupBox.setObjectName("groupBox")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.groupBox)
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout.setContentsMargins(10, 10, 10, 10)

        self.cB_WOB_2 = QtWidgets.QComboBox(self.groupBox)
        self.cB_WOB_2.setMaximumSize(QtCore.QSize(200, 16777215))
        self.cB_WOB_2.setObjectName("cB_WOB_2")

        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.horizontalLayout_3.addWidget(self.cB_WOB_2)
        spacer_item = QtWidgets.QSpacerItem(
            40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum
        )
        self.horizontalLayout_3.addItem(spacer_item)

        self.verticalLayout.addLayout(self.horizontalLayout_3)
        self.verticalLayout_3.addWidget(self.groupBox)

        self.groupBox_2 = QtWidgets.QGroupBox(OilFuncStickSlip)
        self.groupBox_2.setObjectName("groupBox_2")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.groupBox_2)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(10, 10, 10, 10)

        self.label_standard = QtWidgets.QLabel(self.groupBox_2)
        self.label_standard.setText("")
        self.label_standard.setObjectName("label_standard")
        self.label_standard.setAlignment(QtCore.Qt.AlignCenter)
        self.label_standard.setMinimumHeight(120)
        self.label_standard.setMaximumHeight(220)
        self.label_standard.setWordWrap(True)
        self.verticalLayout_2.addWidget(self.label_standard)
        self.verticalLayout_3.addWidget(self.groupBox_2)

        self.btn_layout = QtWidgets.QHBoxLayout()
        self.btn_layout.setObjectName("btn_layout")
        self.btn_layout.setSpacing(10)

        self.btn_Load = QtWidgets.QPushButton(OilFuncStickSlip)
        self.btn_Load.setObjectName("btn_Load")
        self.btn_Load.setFixedHeight(28)
        self.btn_Load.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.btn_layout.addWidget(self.btn_Load)

        spacer_item_mid = QtWidgets.QSpacerItem(
            40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum
        )
        self.btn_layout.addItem(spacer_item_mid)

        self.btn_apply = QtWidgets.QPushButton(OilFuncStickSlip)
        self.btn_apply.setObjectName("btn_apply")
        self.btn_apply.setFixedHeight(28)
        self.btn_apply.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.btn_layout.addWidget(self.btn_apply)

        self.btn_Transfer = QtWidgets.QPushButton(OilFuncStickSlip)
        self.btn_Transfer.setObjectName("btn_Transfer")
        self.btn_Transfer.setFixedHeight(28)
        self.btn_Transfer.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.btn_layout.addWidget(self.btn_Transfer)

        self.verticalLayout_3.addLayout(self.btn_layout)

        self.label_time_range = QtWidgets.QLabel(OilFuncStickSlip)
        self.label_time_range.setObjectName("label_time_range")
        self.label_time_range.setAlignment(QtCore.Qt.AlignCenter)
        self.label_time_range.setMinimumHeight(40)
        self.label_time_range.setStyleSheet(
            "border: 1px solid #cccccc; border-radius: 4px; padding: 5px;"
        )
        self.verticalLayout_3.addWidget(self.label_time_range)

        self.widget_plot_placeholder = QtWidgets.QWidget(OilFuncStickSlip)
        self.widget_plot_placeholder.setObjectName("widget_plot_placeholder")
        self.widget_plot_placeholder.setMinimumHeight(400)
        self.verticalLayout_3.addWidget(self.widget_plot_placeholder)

        self.retranslateUi(OilFuncStickSlip)
        QtCore.QMetaObject.connectSlotsByName(OilFuncStickSlip)

    def retranslateUi(self, OilFuncStickSlip):
        _translate = QtCore.QCoreApplication.translate
        OilFuncStickSlip.setWindowTitle(_translate("OilFuncStickSlip", "粘滑分析"))
        self.groupBox.setTitle(_translate("OilFuncStickSlip", "转速 (RPM)"))
        self.groupBox_2.setTitle(_translate("OilFuncStickSlip", "标准规范"))
        self.btn_Load.setText(_translate("OilFuncStickSlip", "Load"))
        self.btn_apply.setText(_translate("OilFuncStickSlip", "Calculate"))
        self.btn_Transfer.setText(_translate("OilFuncStickSlip", "Transfer"))
        self.label_time_range.setText(_translate("OilFuncStickSlip", "当前选中时间：无"))
