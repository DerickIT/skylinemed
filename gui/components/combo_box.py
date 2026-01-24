# -*- coding: utf-8 -*-
from typing import List, Optional, Tuple, Any

from PySide6.QtCore import Qt, QSortFilterProxyModel, QSize, QRect, Signal
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QComboBox, QStyledItemDelegate, QAbstractItemView, QCompleter, QStyle


class FilterProxyModel(QSortFilterProxyModel):
    """
    通用过滤模型，支持不区分大小写的模糊搜索
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setFilterRole(Qt.DisplayRole) # 过滤显示的文本

    def filterAcceptsRow(self, source_row, source_parent):
        # 可以在这里增加更高级的过滤逻辑，例如拼音首字母匹配（如果需要）
        # 目前使用默认的包含匹配
        return super().filterAcceptsRow(source_row, source_parent)


class DoctorItemDelegate(QStyledItemDelegate):
    """
    医生列表项的自定义渲染器
    布局：[ 医生姓名           (余号) ￥价格 ]
    """
    def paint(self, painter: QPainter, option, index):
        painter.save()

        # 1. 绘制背景
        if option.state & QStyle.State_Selected:
            # 选中态：淡蓝色背景
            painter.fillRect(option.rect, QColor("#E5F1FB"))
        elif option.state & QStyle.State_MouseOver:
             # 悬停态
            painter.fillRect(option.rect, QColor("#F5F5F7"))
        else:
            # 默认背景
            painter.fillRect(option.rect, option.palette.base())

        # 2. 获取数据
        # UserRole: ID (不显示)
        # UserRole + 1: 余号 (Left Num)
        # UserRole + 2: 费用 (Fee)
        name = index.data(Qt.DisplayRole)
        left_num = index.data(Qt.UserRole + 1)
        fee = index.data(Qt.UserRole + 2)

        rect = option.rect
        # 增加左右内边距
        content_rect = rect.adjusted(12, 0, -12, 0)
        
        # 3. 绘制左侧：医生姓名
        font_name = option.font
        font_name.setPixelSize(14)
        font_name.setBold(True)
        painter.setFont(font_name)
        painter.setPen(QColor("#1D1D1F")) # 深黑
        
        # 垂直居中
        painter.drawText(content_rect, Qt.AlignLeft | Qt.AlignVCenter, name)

        # 4. 绘制右侧：余号和价格
        # 如果是普通选项（也就是有余号信息的）
        if left_num is not None:
            # 准备字体
            font_detail = option.font
            font_detail.setPixelSize(12)
            font_detail.setBold(False)
            painter.setFont(font_detail)
            
            # --- 绘制价格 (最右侧) ---
            right_offset = 0
            if fee:
                fee_text = f"￥{fee}"
                painter.setPen(QColor("#86868B")) # 灰色价格
                
                fm = QFontMetrics(font_detail)
                fee_width = fm.horizontalAdvance(fee_text)
                
                fee_rect = QRect(content_rect.right() - fee_width, content_rect.top(), fee_width, content_rect.height())
                painter.drawText(fee_rect, Qt.AlignRight | Qt.AlignVCenter, fee_text)
                
                # 更新偏移量，防止重叠
                right_offset = fee_width + 16

            # --- 绘制余号 (价格左侧) ---
            try:
                count = int(left_num)
                has_ticket = count > 0
            except:
                count = 0
                has_ticket = False
            
            avail_text = f"余 {count}" if count >= 0 else str(left_num)
            
            # 颜色策略
            if has_ticket:
                 painter.setPen(QColor("#00D26A")) # 绿色
                 # 可以加一个 ✅ 前缀? 暂时从简
            else:
                 painter.setPen(QColor("#999999")) # 灰色
            
            # 绘制区域
            avail_rect = QRect(content_rect.left(), content_rect.top(), content_rect.width() - right_offset, content_rect.height())
            painter.drawText(avail_rect, Qt.AlignRight | Qt.AlignVCenter, avail_text)

        painter.restore()

    def sizeHint(self, option, index):
        # 增加行高，更易点击
        return QSize(option.rect.width(), 44)


class FilterableComboBox(QComboBox):
    """
    支持模糊搜索和自定义渲染的高级下拉框
    """
    def __init__(self, parent=None, use_doctor_delegate=False):
        super().__init__(parent)
        
        # 1. 基础设置
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCompleter(None) # 禁用原生补全，使用我们的 Proxy 过滤
        
        # 2. 模型设置 (Source -> Proxy -> View)
        self.m_model = QStandardItemModel(self)
        self.proxy = FilterProxyModel(self)
        self.proxy.setSourceModel(self.m_model)
        self.setModel(self.proxy)
        
        # 3. 视图优化
        # 使用 StyledItemDelegate 渲染
        if use_doctor_delegate:
            self.setItemDelegate(DoctorItemDelegate(self))
        
        self.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.view().setStyleSheet("""
            QListView {
                border: 1px solid #E5E5EA;
                border-radius: 8px;
                background-color: white;
                outline: none;
            }
            QListView::item:selected {
                background-color: #E5F1FB;
                color: black;
            }
        """)
        
        # 4. 信号连接
        # 监听输入框变化，实时过滤
        self.lineEdit().textEdited.connect(self._on_search_text_changed)

    def _on_search_text_changed(self, text):
        # 设置过滤规则
        self.proxy.setFilterFixedString(text)
        
        # 如果有文本且未弹出，则弹出列表
        if text and self.count() > 0:
            self.showPopup()

    def setCurrentIndex(self, index):
        super().setCurrentIndex(index)
        self._sync_text()

    def _sync_text(self):
        # 确保输入框显示当前选中的文本
        if self.currentIndex() >= 0:
            text = self.itemText(self.currentIndex())
            self.setEditText(text)
            # 移动光标到末尾
            if self.lineEdit():
                self.lineEdit().setCursorPosition(len(text))

    def showPopup(self):
        super().showPopup()
        # 确保弹出时宽度足够
        width = self.width()
        self.view().setMinimumWidth(width)

    def fast_add_items(
        self,
        items: List[Tuple],
        static_items: Optional[List[Tuple]] = None,
        select_first: bool = True,
    ):
        """
        快速添加数据
        items: [(Text, DataID, LeftNum?, Fee?), ...]
        """
        self.clear()
        self.m_model.clear()
        
        # 添加静态项 (如 "全部医生")
        if static_items:
            for entry in static_items:
                self._add_single_item(entry)
                
        # 添加动态项
        for entry in items:
            self._add_single_item(entry)
            
        # 默认选中第一项
        if select_first and self.count() > 0:
            self.setCurrentIndex(0)
            
    def _add_single_item(self, entry):
        # 解析数据
        # 格式可能是 (text, id) 或 (text, id, left_num, fee)
        text = str(entry[0])
        data_id = entry[1]
        
        item = QStandardItem(text)
        item.setData(data_id, Qt.UserRole)
        
        if len(entry) > 2:
            item.setData(entry[2], Qt.UserRole + 1) # Left Num
        if len(entry) > 3:
            item.setData(entry[3], Qt.UserRole + 2) # Fee
            
        self.m_model.appendRow(item)
