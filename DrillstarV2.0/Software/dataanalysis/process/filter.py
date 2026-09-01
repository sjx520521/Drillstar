import os
from PyQt5.QtWidgets import (
    QWidget, QMessageBox, QHBoxLayout, QLabel
)
from dataanalysis.ui.ProcessFilter_ui import Ui_Filter
import pandas as pd
import numpy as np
from dataanalysis.buttonNode import ButtonNode

class Win_ProcessFilter(QWidget):
    """
    数据滤波处理类
    支持均值滤波、中值滤波、平滑滤波（加权平均），自动筛选数值列进行处理
    修复了数据维度不匹配、行数不一致的问题
    """
    def __init__(self, node: ButtonNode):
        super().__init__()
        self.ui = Ui_Filter()
        self.ui.setupUi(self)
        self.ui.btn_Load.setText("Load")
        self.ui.btn_Transfer.setText("Transfer")
        self.setWindowTitle("DataAnalysis [filter]")

        # 初始化变量
        self.node = node
        self.df = pd.DataFrame()  # 原始数据
        self.df_smooth = pd.DataFrame()  # 滤波后数据
        self.need_filter_columns = []  # 需要滤波的数值列名

        # 初始化UI控件
        self._init_ui()

        # 绑定信号与槽
        self.ui.btn_Load.clicked.connect(self.on_Load)
        self.ui.btn_Transfer.clicked.connect(self.on_Transfer)

    def _init_ui(self):
        """初始化UI控件默认状态"""
        # 设置窗口大小输入框默认值
        self.ui.lE_WindowSize.setText("5")
        # 设置滤波类型下拉框默认值（若UI中未设置）
        if self.ui.cB_FilterType.count() > 0:
            self.ui.cB_FilterType.setCurrentIndex(0)
        # 清空布局缓存
        self.need_filter_columns.clear()

    def on_Load(self):
        """加载上游节点数据"""
        try:
            if self.node.getInput(0) is None:
                self.node.markDirty()
                self.node.markInvalid()
                QMessageBox.warning(self, "警告", "上游节点无数据输入！")
                return

            res = self.node.getInput(0).serialize()
            self.df = res.get('value', pd.DataFrame())

            if self.df.empty:
                self.node.markInvalid()
                QMessageBox.warning(self, "警告", "加载的数据为空！")
                return

            self.node.eval()
            self.on_initUI()
            QMessageBox.information(self, "成功", f"数据加载完成：共{len(self.df)}行 × {len(self.df.columns)}列")

        except Exception as e:
            self.node.markInvalid()
            QMessageBox.critical(self, "错误", f"加载数据失败：{str(e)}")

    def on_initUI(self):
        """根据数据列更新UI显示，筛选数值列"""
        # 清空原有布局和列列表
        self._clear_layout(self.ui.verticalLayout_data)
        self.need_filter_columns.clear()

        # 遍历列，筛选数值列
        for col in self.df.columns:
            # 排除非数值列
            if pd.api.types.is_numeric_dtype(self.df[col]):
                # 创建水平布局，显示列名
                h_layout = QHBoxLayout()
                col_label = QLabel(col)
                h_layout.addWidget(col_label)
                self.ui.verticalLayout_data.addLayout(h_layout)
                # 将数值列加入滤波列表
                self.need_filter_columns.append(col)

        if not self.need_filter_columns:
            QMessageBox.warning(self, "警告", "数据中无数值列，无法进行滤波！")

    def _clear_layout(self, layout):
        """清空布局中的所有控件和子布局，避免内存泄漏"""
        if layout is None:
            return
        while layout.count() > 0:
            item = layout.takeAt(0)
            # 若为控件，删除控件
            if item.widget():
                item.widget().deleteLater()
            # 若为布局，递归清空
            elif item.layout():
                self._clear_layout(item.layout())
            # 删除布局项
            del item

    def on_Transfer(self):
        """将滤波后的数据传递给下游节点"""
        try:
            self.on_FilterSetting()
            # 检查滤波后数据是否为空
            if self.df_smooth.empty:
                QMessageBox.warning(self, "警告", "滤波后数据为空，无法传递！")
                return
            # 传递数据给节点
            if self.node.LoadData(self.df_smooth):
                self.node.eval()
                self.node.evalChildren()
                QMessageBox.information(self, "成功", "滤波后数据已传递给下游节点！")
            else:
                QMessageBox.critical(self, "错误", "数据传递失败！")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"数据传递失败：{str(e)}")

    def on_FilterSetting(self):
        """根据选择的滤波类型处理数据（核心修复：解决维度不匹配）"""
        # 处理窗口大小输入
        try:
            window_size = int(self.ui.lE_WindowSize.text())
        except ValueError:
            QMessageBox.critical(self, "错误", "窗口大小必须为整数！")
            self.ui.lE_WindowSize.setText("5")
            return

        # 筛选数值列（删除非数值列）
        del_columns = list(set(self.df.columns) - set(self.need_filter_columns))
        df_numeric = self.df.drop(columns=del_columns, errors='ignore').copy()

        # 获取滤波类型
        filter_type = self.ui.cB_FilterType.currentText()

        # -------------------------- 核心修复：保证滤波后行数与原数据一致 --------------------------
        original_index = df_numeric.index  # 保存原始索引
        original_shape = df_numeric.shape  # 保存原始形状

        # 根据滤波类型处理数据
        if filter_type == '均值滤波':
            if window_size < 2:
                QMessageBox.critical(self, "错误", "均值滤波窗口大小必须≥2！")
                return
            # 滚动均值滤波：使用min_periods=1保证行数不变，填充少量缺失值
            df_smooth_numeric = df_numeric.rolling(
                window_size,
                min_periods=1,  # 至少1个数据点就计算，保证行数不变
                center=True     # 窗口居中，减少首尾缺失
            ).mean()

        elif filter_type == '中值滤波':
            if window_size < 3 or window_size % 2 == 0:
                QMessageBox.critical(self, "错误", "中值滤波窗口大小必须为≥3的奇数！")
                return
            # 中值滤波：使用min_periods=1保证行数不变
            df_smooth_numeric = df_numeric.rolling(
                window_size,
                min_periods=1,
                center=True
            ).median()

        elif filter_type == '平滑滤波':
            if window_size < 2:
                QMessageBox.critical(self, "错误", "平滑滤波窗口大小必须≥2！")
                return
            # 加权平均平滑滤波
            weights = np.linspace(1, 2, window_size)
            weights = weights / weights.sum()
            # 自定义滚动函数，保证行数不变
            def weighted_average(x):
                if len(x) < len(weights):
                    # 不足窗口大小时，使用现有数据的权重归一化
                    w = weights[:len(x)] / weights[:len(x)].sum()
                    return np.dot(x, w)
                return np.dot(x, weights)
            # 滚动应用加权平均
            df_smooth_numeric = df_numeric.rolling(
                window_size,
                min_periods=1,
                center=True
            ).apply(weighted_average, raw=True)

        # 填充缺失值（保证无NaN，行数不变）
        df_smooth_numeric = df_smooth_numeric.fillna(method='bfill').fillna(method='ffill')

        # 强制恢复原始索引和形状（防止意外的行数变化）
        df_smooth_numeric = df_smooth_numeric.reindex(original_index)

        # -------------------------- 合并非数值列：按索引对齐，保证维度一致 --------------------------
        self.df_smooth = df_smooth_numeric.copy()

        # 若有非数值列，按索引合并（inner连接保证行数一致）
        if del_columns:
            df_non_numeric = self.df[del_columns].copy()
            # 按索引内连接，仅保留两者共有的行
            self.df_smooth = pd.concat(
                [self.df_smooth, df_non_numeric],
                axis=1,
                join='inner'  # 核心：内连接避免维度不匹配
            )

        # 恢复原始数据的列顺序（提升用户体验）
        self.df_smooth = self.df_smooth.reindex(columns=self.df.columns)

        # 最终检查：确保行数与原数据一致
        if len(self.df_smooth) != len(self.df):
            QMessageBox.warning(self, "警告", f"滤波后数据行数({len(self.df_smooth)})与原数据({len(self.df)})不一致，已自动对齐！")
            # 强制截断/填充到原数据行数
            self.df_smooth = self.df_smooth.head(len(self.df))
