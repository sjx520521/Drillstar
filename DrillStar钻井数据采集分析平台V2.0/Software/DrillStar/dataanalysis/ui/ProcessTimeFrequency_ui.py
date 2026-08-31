# -*- coding: utf-8 -*-

from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_TimeFrequency(object):
    def setupUi(self, TimeFrequency):
        TimeFrequency.setObjectName("TimeFrequency")
        TimeFrequency.resize(1150, 823)
        self.verticalLayout_3 = QtWidgets.QVBoxLayout(TimeFrequency)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.splitter = QtWidgets.QSplitter(TimeFrequency)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setObjectName("splitter")
        self.groupBox_2 = QtWidgets.QGroupBox(self.splitter)
        self.groupBox_2.setMaximumSize(QtCore.QSize(300, 16777215))
        self.groupBox_2.setObjectName("groupBox_2")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.groupBox_2)
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout_para = QtWidgets.QVBoxLayout()
        self.verticalLayout_para.setObjectName("verticalLayout_para")
        self.verticalLayout.addLayout(self.verticalLayout_para)

        # 采样率标签
        self.label_sample_rate = QtWidgets.QLabel(self.groupBox_2)
        self.label_sample_rate.setObjectName("label_sample_rate")
        self.verticalLayout.addWidget(self.label_sample_rate)

        # 采样率输入框
        self.lE_Sample = QtWidgets.QLineEdit(self.groupBox_2)
        self.lE_Sample.setObjectName("lE_Sample")
        self.verticalLayout.addWidget(self.lE_Sample)

        # 时间范围显示标签（支持换行）
        self.label_time_range = QtWidgets.QLabel(self.groupBox_2)
        self.label_time_range.setObjectName("label_time_range")
        self.label_time_range.setWordWrap(True)  # 自动换行
        self.label_time_range.setMaximumWidth(280)  # 限制宽度触发换行
        self.verticalLayout.addWidget(self.label_time_range)

        # 显示按钮
        self.btn_Show = QtWidgets.QPushButton(self.groupBox_2)
        self.btn_Show.setObjectName("btn_Show")
        self.verticalLayout.addWidget(self.btn_Show)

        spacerItem = QtWidgets.QSpacerItem(20, 422, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem)

        self.groupBox = QtWidgets.QGroupBox(self.splitter)
        self.groupBox.setObjectName("groupBox")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.groupBox)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.verticalLayout_data = QtWidgets.QVBoxLayout()
        self.verticalLayout_data.setObjectName("verticalLayout_data")
        self.verticalLayout_2.addLayout(self.verticalLayout_data)

        self.verticalLayout_3.addWidget(self.splitter)

        self.widget = QtWidgets.QWidget(TimeFrequency)
        self.widget.setMaximumSize(QtCore.QSize(16777215, 40))
        self.widget.setObjectName("widget")
        self.verticalLayout_4 = QtWidgets.QVBoxLayout(self.widget)
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")

        # Load按钮（增大高度）
        self.btn_Load = QtWidgets.QPushButton(self.widget)
        self.btn_Load.setMinimumHeight(30)
        self.btn_Load.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.btn_Load.setObjectName("btn_Load")
        self.horizontalLayout.addWidget(self.btn_Load)

        spacerItem1 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem1)

        self.btn_Transfer = QtWidgets.QPushButton(self.widget)
        self.btn_Transfer.setObjectName("btn_Transfer")
        self.horizontalLayout.addWidget(self.btn_Transfer)

        self.verticalLayout_4.addLayout(self.horizontalLayout)
        self.verticalLayout_3.addWidget(self.widget)

        self.retranslateUi(TimeFrequency)
        QtCore.QMetaObject.connectSlotsByName(TimeFrequency)

    def retranslateUi(self, TimeFrequency):
        _translate = QtCore.QCoreApplication.translate
        TimeFrequency.setWindowTitle(_translate("TimeFrequency", "Form"))
        self.groupBox_2.setTitle(_translate("TimeFrequency", "数据"))
        self.label_sample_rate.setText(_translate("TimeFrequency", "采样频率(Hz)："))
        self.lE_Sample.setPlaceholderText(_translate("TimeFrequency", "请输入采样率，默认1000"))
        self.label_time_range.setText(_translate("TimeFrequency", "当前选中时间：无"))
        self.btn_Show.setText(_translate("TimeFrequency", "显示"))
        self.groupBox.setTitle(_translate("TimeFrequency", "绘图区"))
        self.btn_Load.setText(_translate("TimeFrequency", "Load"))
        self.btn_Transfer.setText(_translate("TimeFrequency", "Transfer"))