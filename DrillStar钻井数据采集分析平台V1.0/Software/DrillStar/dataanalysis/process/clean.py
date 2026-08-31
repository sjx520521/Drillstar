import os
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QMessageBox, QHBoxLayout, QLabel, QCheckBox
)
from dataanalysis.ui.ProcessClean_ui import Ui_Clean
from dataanalysis.buttonNode import ButtonNode

class Win_ProcessClean(QWidget):
    """
    数据清洗处理类（纯3σ法，修复索引和过滤Bug）
    """
    def __init__(self, node: ButtonNode):
        super().__init__()
        self.ui = Ui_Clean()
        self.ui.setupUi(self)
        self.ui.btn_Load.setText("Load")
        self.ui.btn_Clean.setText("Calculate")
        self.ui.btn_Transfer.setText("Transfer")
        self.setWindowTitle("DataAnalysis [clean]")

        # 核心变量
        self.node = node
        self.df = pd.DataFrame()  # 原始数据
        self.df_clean = pd.DataFrame()  # 清洗后数据
        self.column_checkboxes = {}  # 列选择复选框字典

        # 初始化
        self._init_ui()
        self._bind_signals()

    def _init_ui(self):
        """初始化UI控件默认状态"""
        if self.ui.cB_CleanType.count() > 0:
            self.ui.cB_CleanType.setCurrentIndex(0)

    def _bind_signals(self):
        """绑定按钮信号与槽函数"""
        self.ui.btn_Load.clicked.connect(self.on_Load)
        self.ui.btn_Clean.clicked.connect(self.on_Clean)
        self.ui.btn_Transfer.clicked.connect(self.on_Transfer)

    def _reset_state(self):
        """重置数据和UI状态（支持重新Load）"""
        self.df = pd.DataFrame()
        self.df_clean = pd.DataFrame()
        self._clear_layout(self.ui.verticalLayout_data)
        self.column_checkboxes.clear()

    def _clear_layout(self, layout):
        """清空布局中的所有控件和子布局"""
        if layout is None:
            return
        while layout.count() > 0:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
            del item

    def on_Load(self):
        """加载上游节点数据（支持重新加载）"""
        try:
            self._reset_state()

            # 检查上游节点输入
            input_node = self.node.getInput(0)
            if input_node is None:
                QMessageBox.warning(self, "警告", "上游节点无数据输入！")
                return

            # 获取数据
            res = input_node.serialize()
            self.df = res.get('value', pd.DataFrame())

            if self.df.empty:
                QMessageBox.warning(self, "警告", "加载的数据为空！")
                return

            # 更新列选择UI
            self.on_initUI()

            QMessageBox.information(self, "成功",
                                    f"数据加载完成：共{len(self.df)}行 × {len(self.df.columns)}列")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载数据失败：{str(e)}")

    def on_initUI(self):
        """根据数据列更新UI显示"""
        # 保存之前的选中状态
        previous_selected = [col for col, cb in self.column_checkboxes.items() if cb.isChecked()]
        self._clear_layout(self.ui.verticalLayout_data)

        # 遍历列创建复选框
        for col in self.df.columns:
            h_layout = QHBoxLayout()
            cb = QCheckBox()
            cb.setChecked(col in previous_selected if previous_selected else True)
            col_label = QLabel(col)

            h_layout.addWidget(cb)
            h_layout.addWidget(col_label)
            self.ui.verticalLayout_data.addLayout(h_layout)
            self.column_checkboxes[col] = cb

        if not self.df.columns.tolist():
            QMessageBox.warning(self, "警告", "数据中无列数据，无法进行清洗！")

    def on_Clean(self):
        """执行数据清洗（核心方法，恢复文本判断+纯3σ法）"""
        try:
            if self.df.empty:
                QMessageBox.warning(self, "警告", "无数据可清洗！")
                return

            # 获取选中的列
            selected_cols = [col for col, cb in self.column_checkboxes.items() if cb.isChecked()]
            if not selected_cols:
                QMessageBox.warning(self, "警告", "未选择任何列进行清洗！")
                return

            # 复制原始数据，避免累积修改
            self.df_clean = self.df[selected_cols].copy()
            original_shape = self.df_clean.shape

            # 筛选数值列
            selected_numeric_cols = self.df_clean.select_dtypes(include=[np.number]).columns

            # 统计清洗前的缺失值和异常值
            before_missing = self.df_clean.isnull().sum().sum()
            before_outliers = self._count_outliers_3sigma(self.df_clean, selected_numeric_cols)

            # 恢复原始文本判断逻辑（关键：和你最初的代码一致）
            clean_type = self.ui.cB_CleanType.currentText()
            clean_type_simplified = clean_type.split('(')[0].strip()
            if clean_type_simplified == '缺失值处理':
                self._handle_missing_values()
            elif clean_type_simplified == '异常值处理':
                self._handle_outliers_3sigma()  # 纯3σ法，无多余过滤
            elif clean_type_simplified == '一键清洗':
                self._handle_missing_values()
                self._handle_outliers_3sigma()

            # 合并非选中列
            unselected_cols = [col for col in self.df.columns if col not in selected_cols]
            if unselected_cols:
                self.df_clean = pd.concat(
                    [self.df_clean, self.df[unselected_cols]],
                    axis=1,
                    join='inner'
                )

            # 恢复列顺序
            self.df_clean = self.df_clean.reindex(columns=self.df.columns)

            # 统计清洗后的数据
            after_missing = self.df_clean.isnull().sum().sum()
            after_outliers = self._count_outliers_3sigma(self.df_clean, selected_numeric_cols)

            # 打印对比（调试用）
            self._print_col_stats(selected_numeric_cols)

            # 弹窗提示
            QMessageBox.information(self, "成功",
                                    f"清洗完成！\n原始数据：{original_shape[0]}行 × {original_shape[1]}列\n"
                                    f"清洗后数据：{self.df_clean.shape[0]}行 × {self.df_clean.shape[1]}列\n"
                                    f"缺失值：{before_missing}个 → {after_missing}个\n"
                                    f"异常值：{before_outliers}个 → {after_outliers}个")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"清洗数据失败：{str(e)}")

    def _print_col_stats(self, numeric_cols):
        """打印列的统计信息（调试用）"""
        for col in numeric_cols:
            before = self.df[col].describe()
            after = self.df_clean[col].describe()
            print(f"\n列 {col} 清洗前后对比：")
            print(f"原始数据：最大值={before['max']:.2f}，最小值={before['min']:.2f}")
            print(f"清洗后：最大值={after['max']:.2f}，最小值={after['min']:.2f}")

    def _count_outliers_3sigma(self, df, numeric_cols):
        """纯3σ统计异常值数量（与处理逻辑完全一致）"""
        outlier_count = 0
        for col in numeric_cols:
            data = df[col].dropna().copy()
            if len(data) < 3:
                continue
            mean = data.mean()
            std = data.std(ddof=0)
            lower = mean - 3 * std
            upper = mean + 3 * std
            outliers = (data < lower) | (data > upper)
            outlier_count += outliers.sum()
        return outlier_count

    def _handle_missing_values(self):
        """处理缺失值（ffill + bfill + 均值/众数兜底）"""
        for col in self.df_clean.columns:
            if pd.api.types.is_numeric_dtype(self.df_clean[col]):
                self.df_clean[col] = self.df_clean[col].ffill().bfill()
                self.df_clean[col] = self.df_clean[col].fillna(self.df_clean[col].mean())
            else:
                self.df_clean[col] = self.df_clean[col].ffill().bfill()
                mode_series = self.df_clean[col].mode()
                fill_value = mode_series.iloc[0] if not mode_series.empty else ""
                self.df_clean[col] = self.df_clean[col].fillna(fill_value)

    def _handle_outliers_3sigma(self):
        """
        纯3σ法处理异常值（修复所有Bug）
        1. 移除MAD预过滤，避免干扰
        2. 直接基于原始有效数据计算3σ阈值
        3. 正确标记异常值并填充
        """
        for col in self.df_clean.columns:
            if not pd.api.types.is_numeric_dtype(self.df_clean[col]):
                continue

            # 原始数据（保留全部索引）
            col_data = self.df_clean[col].copy()
            # 仅剔除空值，不做任何过滤
            valid_data = col_data.dropna()
            if len(valid_data) < 3:
                continue

            # 计算纯3σ阈值（仅计算一次，非迭代，避免阈值过度宽松）
            mean = valid_data.mean()
            std = valid_data.std(ddof=0)
            lower = mean - 3 * std
            upper = mean + 3 * std

            # 直接标记原始数据中的异常值（关键：索引完全匹配）
            outlier_mask = (col_data < lower) | (col_data > upper)
            print(f"列 {col} 纯3σ法识别异常值数量：{outlier_mask.sum()}")

            # 处理异常值：先设为NaN，再用前向+后向填充，最后用边界值兜底
            if outlier_mask.any():
                # 步骤1：将异常值置为NaN
                col_data[outlier_mask] = np.nan
                # 步骤2：时序插值填充（保留时序特征）
                col_data = col_data.interpolate(method='linear').ffill().bfill()
                # 步骤3：边界值兜底（确保无值超出3σ）
                col_data = np.where(col_data < lower, lower, col_data)
                col_data = np.where(col_data > upper, upper, col_data)
                # 写回数据
                self.df_clean[col] = col_data

    def on_Transfer(self):
        """将清洗后的数据传递给下游节点（支持重复传递）"""
        try:
            if self.df_clean.empty:
                QMessageBox.warning(self, "警告", "清洗后数据为空，无法传递！")
                return

            if self.node.LoadData(self.df_clean):
                self.node.eval()
                self.node.evalChildren()
                QMessageBox.information(self, "成功", "清洗后数据已传递给下游节点！")
            else:
                QMessageBox.critical(self, "错误", "数据传递失败！")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"数据传递失败：{str(e)}")
