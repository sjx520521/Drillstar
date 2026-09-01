from nodeeditor.node_graphics_node import QDMGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_node import Node
from nodeeditor.utils import dumpException
from PyQt5.QtGui import QImage, QIcon
from PyQt5.QtCore import QRectF, QSize, Qt
from PyQt5.QtWidgets import (
    QApplication,
    QAction,
    QGraphicsScene,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class ButtonGraphicsNode(QDMGraphicsNode):
    def initSizes(self):
        super().initSizes()
        self.width = 120
        self.height = 180

    def initAssets(self):
        super().initAssets()
        self.icons = QImage("icon/status_icons.png")

    def paint(self, painter, QStyleOptionGraphicsItem, widget=None):
        super().paint(painter, QStyleOptionGraphicsItem, widget)

        offset = 24.0
        if self.node.isDirty():
            offset = 0.0
        if self.node.isInvalid():
            offset = 48.0

        painter.drawImage(
            QRectF(-10, -10, 24.0, 24.0),
            self.icons,
            QRectF(offset, 0, 24.0, 24.0),
        )

    def delete_node(self):
        try:
            node = self.node
            scene = node.scene

            if scene is None:
                print(f"警告：节点【{node.title}】所属场景为空，无需删除")
                return

            scene.removeNode(node)

            if isinstance(scene, QGraphicsScene):
                scene.invalidate()
            if hasattr(scene, "views") and callable(scene.views):
                for view in scene.views():
                    view.update()
            QApplication.processEvents()

            print(f"节点【{node.title}】已成功删除")

        except Exception as e:
            dumpException(e)

    def contextMenuEvent(self, event):
        try:
            event.accept()
            view = None
            if self.scene() and self.scene().views():
                view = self.scene().views()[0]

            if view and hasattr(view, "last_mouse_global_pos") and view.last_mouse_global_pos:
                screen_pos = view.last_mouse_global_pos
            else:
                screen_pos = event.screenPos().toPoint()

            menu = QMenu()
            delete_action = QAction("删除节点", None)
            delete_action.triggered.connect(self.delete_node)
            menu.addAction(delete_action)
            menu.exec_(screen_pos)

        except Exception as e:
            dumpException(e)


class ButtonContent(QDMNodeContentWidget):
    def initUI(self):
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet("background: transparent;border:0px")
        self.setLayout(self.layout)

        self.btn = QPushButton()
        self.btn.setStyleSheet("background: transparent;border:0px")
        self.btn.setContextMenuPolicy(Qt.NoContextMenu)
        self.layout.addWidget(self.btn)

        self.update_icon()

    def update_icon(self):
        if hasattr(self.node, "icon") and self.node.icon:
            icon = QIcon(self.node.icon)
            self.btn.setIcon(icon)
            self.btn.setIconSize(QSize(64, 64))
        if hasattr(self.node, "content_label_objname"):
            self.btn.setObjectName(self.node.content_label_objname)


class ButtonNode(Node):
    op_code = 0
    op_title = "CSV导入"
    content_label = ""
    content_label_objname = "node_CSV"
    type_ = "button_node"

    GraphicsNode_class = ButtonGraphicsNode
    NodeContent_class = ButtonContent

    def __init__(
        self,
        scene: "Scene",
        title: str = "Undefined Node",
        inputs: list = [],
        outputs: list = [],
        window=None,
    ):
        self.icon = "icon/csv.png"
        self.content_label_objname = ""
        super().__init__(scene, title, inputs, outputs)

        # 窗口改为懒加载，避免进入数据分析模块时一次性初始化全部功能窗体。
        self.window_factory = window if callable(window) else None
        self.window = None if self.window_factory is not None else window
        self.data = None

        self.markDirty()

    def initInnerClasses(self):
        self.content = ButtonContent(self)
        self.grNode = ButtonGraphicsNode(self)
        self.content.btn.clicked.connect(self.test)
        self.content.update_icon()

    def serialize(self):
        res = super().serialize()
        res["value"] = self.data
        return res

    def LoadData(self, value):
        self.data = value
        return True

    def eval(self, index=0):
        self.markDirty(False)
        self.markInvalid(False)
        return self.data

    def _ensure_window(self):
        if self.window is None and self.window_factory is not None:
            self.window = self.window_factory(self)
        return self.window

    def test(self):
        try:
            window = self._ensure_window()
            if window is None:
                print("---->链接窗口为空")
            else:
                window.show()
                print(f"ButtonNode:{self}")
                print(f"---->打开节点{self.content_label_objname}链接窗口：{window}")
        except Exception as e:
            QMessageBox.critical(None, "错误", f"打开节点窗口失败：{e}")
            dumpException(e)

    def markValid(self):
        self.markInvalid(False)
        if self.grNode:
            self.grNode.update()

    def markInvalid(self, value: bool = True):
        self._invalid = value
        if self.grNode:
            self.grNode.update()

    def markDirty(self, value: bool = True):
        self._dirty = value
        if self.grNode:
            self.grNode.update()

    def isInvalid(self):
        return getattr(self, "_invalid", False)

    def isDirty(self):
        return getattr(self, "_dirty", False)
