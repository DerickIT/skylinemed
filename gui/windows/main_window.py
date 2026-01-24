# -*- coding: utf-8 -*-
import json
import threading
from typing import Optional, List, Dict

from PySide6.QtCore import Qt, QDate, QLocale
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QDateEdit,
    QSizePolicy,
)

from core.client import HealthClient
from gui.components.cards import CardFrame
from gui.components.combo_box import FilterableComboBox
from gui.components.toggle import SegmentedToggle
from gui.components.log_viewer import LogViewer
from gui.utils.paths import get_config_path
from gui.utils.signals import WorkerSignals
from gui.utils.themes import load_stylesheet
from gui.windows.login_dialog import QRLoginDialog


class MainWindow(QMainWindow):
    """91160 智慧分诊助手主窗口 - 企业级 Mac 风格"""

    def __init__(self):
        super().__init__()

        self.client = HealthClient()
        self.signals = WorkerSignals()
        self.cities: List[Dict] = []
        self.is_running = False
        self.is_logged_in = False
        self.login_checked = False
        self.pending_doctor_query = False
        self.pending_hospital_load = False
        self.pending_dep_load = False
        self.grab_stop_event = threading.Event()
        self.grab_thread: Optional[threading.Thread] = None
        self.grab_thread: Optional[threading.Thread] = None
        self.qr_dialog: Optional[QRLoginDialog] = None

        self.saved_state: Dict = {}
        self._load_ui_state()

        self._setup_window()
        self._build_ui()
        self._connect_signals()
        self._init_data()

    def _setup_window(self):
        self.setWindowTitle("91160 智慧分诊助手")
        self.setMinimumSize(1100, 750)
        self.resize(1200, 800)
        self.setStyleSheet(load_stylesheet())

    def _build_ui(self):
        central = QWidget()
        central.setStyleSheet("background-color: #F5F5F7;")
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(30, 20, 30, 30)
        main_layout.setSpacing(20)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 10)
        top_bar.setSpacing(16)

        title = QLabel("🏥 智慧分诊工作台")
        title.setObjectName("title")
        top_bar.addWidget(title)

        top_bar.addStretch()

        self.status_badge = QLabel("未登录")
        self.status_badge.setObjectName("statusBadge")
        self.status_badge.setProperty("status", "warning")
        self.status_badge.setAlignment(Qt.AlignCenter)
        top_bar.addWidget(self.status_badge)

        self.login_btn = QPushButton("扫码连接")
        self.login_btn.setObjectName("secondary")
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.clicked.connect(self.on_login_click)
        top_bar.addWidget(self.login_btn)

        main_layout.addLayout(top_bar)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(24)

        left_card = CardFrame()
        left_card.setFixedWidth(460)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(28, 24, 28, 28)
        left_layout.setSpacing(24)

        config_header = QHBoxLayout()
        section_title = QLabel("⚡ 极速挂号配置")
        section_title.setObjectName("sectionTitle")
        config_header.addWidget(section_title)
        config_header.addStretch()
        left_layout.addLayout(config_header)

        form_layout = QVBoxLayout()
        form_layout.setSpacing(12)

        form_layout.addWidget(self._create_field_label("所在城市"))
        self.city_combo = FilterableComboBox(self)
        self.city_combo.setPlaceholderText("选择城市")
        self.city_combo.setCursor(Qt.PointingHandCursor)
        self.city_combo.currentIndexChanged.connect(self.on_city_changed)
        form_layout.addWidget(self.city_combo)

        form_layout.addWidget(self._create_field_label("就诊医院"))
        self.hospital_combo = FilterableComboBox(self)
        self.hospital_combo.setPlaceholderText("等待选择城市...")
        self.hospital_combo.setCursor(Qt.PointingHandCursor)
        self.hospital_combo.currentIndexChanged.connect(self.on_hospital_changed)
        form_layout.addWidget(self.hospital_combo)

        form_layout.addSpacing(6)

        form_layout.addWidget(self._create_field_label("目标科室"))
        self.dep_combo = FilterableComboBox(self)
        self.dep_combo.setPlaceholderText("等待选择医院...")
        self.dep_combo.setCursor(Qt.PointingHandCursor)
        self.dep_combo.currentIndexChanged.connect(self.on_dep_changed)
        form_layout.addWidget(self.dep_combo)

        form_layout.addWidget(self._create_field_label("指定医生"))
        self.doctor_combo = FilterableComboBox(self, use_doctor_delegate=True)
        self.doctor_combo.setPlaceholderText("全部医生 (智能筛选)")
        self.doctor_combo.setCursor(Qt.PointingHandCursor)
        self.doctor_combo.currentIndexChanged.connect(lambda: self._save_ui_state())
        form_layout.addWidget(self.doctor_combo)

        form_layout.addWidget(self._create_field_label("就诊人"))
        self.member_combo = FilterableComboBox(self)
        self.member_combo.setPlaceholderText("请先登录获取就诊人")
        self.member_combo.setCursor(Qt.PointingHandCursor)
        self.member_combo.currentIndexChanged.connect(lambda: self._save_ui_state())
        form_layout.addWidget(self.member_combo)

        form_layout.addSpacing(6)

        date_time_grid = QGridLayout()
        date_time_grid.setHorizontalSpacing(12)
        date_time_grid.setVerticalSpacing(6)

        date_label = self._create_field_label("就诊日期")
        time_label = self._create_field_label("时间段")
        date_time_grid.addWidget(date_label, 0, 0)
        date_time_grid.addWidget(time_label, 0, 1)

        self.date_edit = QDateEdit()
        self.date_edit.setLocale(QLocale(QLocale.Chinese, QLocale.China))
        self.date_edit.setCalendarPopup(True)
        today = QDate.currentDate()
        self.date_edit.setMinimumDate(today)
        self.date_edit.setMaximumDate(today.addDays(30))
        self.date_edit.setDate(today.addDays(7))
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setCursor(Qt.PointingHandCursor)
        self.date_edit.dateChanged.connect(self.on_date_changed)
        self.date_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        date_time_grid.addWidget(self.date_edit, 1, 0)

        self.time_toggle = SegmentedToggle([("上午", "am"), ("下午", "pm")])
        self.time_toggle.set_selected(["am", "pm"])
        self.time_toggle.selectionDatachanged.connect(lambda: self._save_ui_state())
        self.time_toggle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        date_time_grid.addWidget(self.time_toggle, 1, 1)

        date_time_grid.setColumnStretch(0, 1)
        date_time_grid.setColumnStretch(1, 1)

        form_layout.addLayout(date_time_grid)

        left_layout.addLayout(form_layout)
        left_layout.addStretch()

        self.start_btn = QPushButton("🚀 启动自动抢号")
        self.start_btn.setObjectName("primary")
        self.start_btn.setMinimumHeight(56)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self.toggle_grab)
        left_layout.addWidget(self.start_btn)

        content_layout.addWidget(left_card)

        right_card = CardFrame()
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(28, 24, 28, 28)
        right_layout.setSpacing(16)

        log_header = QHBoxLayout()
        log_title = QLabel("📜 运行日志")
        log_title.setObjectName("sectionTitle")
        log_header.addWidget(log_title)
        log_header.addStretch()

        clear_btn = QPushButton("清空")
        clear_btn.setObjectName("secondary")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self.clear_logs)
        log_header.addWidget(clear_btn)

        right_layout.addLayout(log_header)

        self.log_view = LogViewer()
        right_layout.addWidget(self.log_view)

        content_layout.addWidget(right_card)

        main_layout.addLayout(content_layout)

    def _create_field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _connect_signals(self):
        self.signals.log.connect(self.log_view.append_log)
        self.signals.hospitals_loaded.connect(self._update_hospitals)
        self.signals.deps_loaded.connect(self._update_deps)
        self.signals.doctors_loaded.connect(self._update_doctors)
        self.signals.members_loaded.connect(self._update_members)
        self.signals.login_status.connect(self._update_login_status)
        self.signals.qr_image.connect(self._show_qr_image)
        self.signals.qr_status.connect(self._update_qr_status)
        self.signals.qr_close.connect(self._close_qr_dialog)
        self.signals.update_button.connect(self._update_start_button)

    def _init_data(self):
        self.log("正在初始化...")

        cities_file = get_config_path("cities.json")
        if cities_file.exists():
            with cities_file.open("r", encoding="utf-8") as f:
                self.cities = json.load(f)
                items = [(city["name"], city["cityId"]) for city in self.cities]
                self.city_combo.fast_add_items(items, select_first=False)
            self.log(f"已加载 {len(self.cities)} 个城市")

            restored_city = False
            if self.saved_state.get("city_id"):
                restored_city = self._try_restore_selection(self.city_combo, self.saved_state["city_id"])
            if not restored_city and self.cities:
                self.city_combo.setCurrentIndex(0)
                self._sync_combo_text(self.city_combo)

        if self.saved_state.get("target_date"):
            try:
                saved_date = QDate.fromString(self.saved_state["target_date"], "yyyy-MM-dd")
                if saved_date.isValid() and saved_date >= QDate.currentDate():
                    self.date_edit.setDate(saved_date)
            except Exception:
                pass

        if "time_slots" in self.saved_state:
            slots = self.saved_state["time_slots"]
            self.time_toggle.set_selected(slots)

        def check_login():
            try:
                if self.client.load_cookies():
                    members = self.client.get_members()
                    if members:
                        self.signals.login_status.emit(True)
                        self.signals.members_loaded.emit(members)
                        self.signals.log.emit("登录状态验证成功", "#00D26A")
                    else:
                        self.signals.login_status.emit(False)
                        self.signals.log.emit("Cookie 已过期，请重新登录", "#FF9500")
                else:
                    self.signals.login_status.emit(False)
                    self.signals.log.emit("需要登录", "#FF9500")
            except Exception as e:
                self.signals.log.emit(f"初始化失败: {e}", "#FF3B30")

        threading.Thread(target=check_login, daemon=True).start()

    def log(self, message: str, color: str = "#AAAAAA"):
        self.signals.log.emit(message, color)

    def _emit_grab_log(self, message: str, level: str = "info"):
        color_map = {
            "info": "#AAAAAA",
            "success": "#00D26A",
            "warn": "#FF9500",
            "error": "#FF3B30",
        }
        self.signals.log.emit(message, color_map.get(level, "#AAAAAA"))

    def _build_grab_config(self) -> Dict:
        unit_id = self.hospital_combo.currentData()
        dep_id = self.dep_combo.currentData()
        doctor_id = self.doctor_combo.currentData()
        member_id = self.member_combo.currentData()
        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        return {
            "unit_id": str(unit_id),
            "unit_name": self.hospital_combo.currentText(),
            "dep_id": str(dep_id),
            "dep_name": self.dep_combo.currentText(),
            "doctor_ids": [str(doctor_id)] if doctor_id not in (None, "") else [],
            "member_id": str(member_id),
            "member_name": self.member_combo.currentText(),
            "target_dates": [date_str],
            "member_name": self.member_combo.currentText(),
            "target_dates": [date_str],
            "time_types": self.time_toggle.get_selected_data(),
            "preferred_hours": [],
        }

    def _load_ui_state(self):
        self.saved_state = {}
        config_path = get_config_path("user_state.json")
        if config_path.exists():
            try:
                with config_path.open("r", encoding="utf-8") as f:
                    self.saved_state = json.load(f)
            except Exception as e:
                print(f"加载状态失败: {e}")

    def _save_ui_state(self):
        state = {
            "city_id": self.city_combo.currentData(),
            "unit_id": self.hospital_combo.currentData(),
            "dep_id": self.dep_combo.currentData(),
            "doctor_id": self.doctor_combo.currentData(),
            "member_id": self.member_combo.currentData(),
            "target_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "target_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "time_slots": self.time_toggle.get_selected_data(),
        }

        config_path = get_config_path("user_state.json")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with config_path.open("w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存状态失败: {e}")

    def _try_restore_selection(self, combo: FilterableComboBox, target_id):
        if not target_id:
            return False

    def _try_restore_selection(self, combo: FilterableComboBox, target_id):
        if not target_id:
            return False

        count = combo.count()
        for i in range(count):
            if str(combo.itemData(i)) == str(target_id):
                combo.setCurrentIndex(i)
                self._sync_combo_text(combo)
                return True
        return False

    def _sync_combo_text(self, combo: FilterableComboBox):
        line_edit = combo.lineEdit()
        if not line_edit:
            return
        text = combo.currentText()
        line_edit.setText(text)
        line_edit.setCursorPosition(len(text))

    def clear_logs(self):
        self.log_view.clear()

    def on_city_changed(self, index: int):
        if index < 0:
            return
        city_id = self.city_combo.currentData()
        if not city_id:
            return
        if not self.login_checked:
            if not self.pending_hospital_load:
                self.log("登录状态验证中，稍后自动加载医院", "#FF9500")
            self.pending_hospital_load = True
            return

        self._save_ui_state()
        if not self.is_logged_in:
            self.log("未登录，无法加载医院", "#FF3B30")
            self.pending_hospital_load = True
            return
        self.log(f"正在加载城市 {self.city_combo.currentText()} 的医院...")
        self.hospital_combo.clear()
        self.hospital_combo.addItem("加载中...", "")

        def load():
            try:
                units = self.client.get_hospitals_by_city(city_id)
                self.signals.hospitals_loaded.emit(units)
            except Exception as e:
                self.signals.log.emit(f"加载医院失败: {e}", "#FF3B30")

        threading.Thread(target=load, daemon=True).start()

    def _update_hospitals(self, units: list):
        items = [(u.get("unit_name", ""), u.get("unit_id", "")) for u in units or []]
        self.hospital_combo.fast_add_items(items, select_first=False)
        self.log(f"已加载 {len(items)} 家医院", "#00D26A")

        restored = False
        if self.saved_state.get("unit_id"):
            restored = self._try_restore_selection(self.hospital_combo, self.saved_state["unit_id"])

        if not restored and items:
            self.hospital_combo.setCurrentIndex(0)
            self._sync_combo_text(self.hospital_combo)

    def on_hospital_changed(self, index: int):
        if index < 0:
            return
        unit_id = self.hospital_combo.currentData()
        if not unit_id:
            return
        if not self.login_checked:
            if not self.pending_dep_load:
                self.log("登录状态验证中，稍后自动加载科室", "#FF9500")
            self.pending_dep_load = True
            return

        self._save_ui_state()
        if not self.is_logged_in:
            self.log("未登录，无法加载科室", "#FF3B30")
            self.pending_dep_load = True
            return

        self.log("正在加载科室...")
        self.dep_combo.clear()
        self.dep_combo.addItem("加载中...", "")

        def load():
            try:
                deps = self.client.get_deps_by_unit(unit_id)
                self.signals.deps_loaded.emit(deps)
            except Exception as e:
                self.signals.log.emit(f"加载科室失败: {e}", "#FF3B30")

        threading.Thread(target=load, daemon=True).start()

    def _update_deps(self, deps: list):
        items: List[tuple] = []
        for item in deps or []:
            if isinstance(item, dict) and isinstance(item.get("childs"), list):
                for child in item.get("childs", []):
                    name = child.get("dep_name") or child.get("name", "")
                    dep_id = child.get("dep_id") or child.get("id", "")
                    if name and dep_id not in (None, ""):
                        items.append((name, dep_id))
            elif isinstance(item, dict):
                name = item.get("dep_name") or item.get("name", "")
                dep_id = item.get("dep_id") or item.get("id", "")
                if name and dep_id not in (None, ""):
                    items.append((name, dep_id))
        if not items:
            self.dep_combo.fast_add_items([], static_items=[("暂无科室", "")], select_first=True)
        else:
            self.dep_combo.fast_add_items(items, select_first=False)
        self.log(f"已加载 {len(items)} 个科室", "#00D26A")

        restored = False
        if self.saved_state.get("dep_id"):
            restored = self._try_restore_selection(self.dep_combo, self.saved_state["dep_id"])

        if not restored and items:
            self.dep_combo.setCurrentIndex(0)
            self._sync_combo_text(self.dep_combo)

    def on_dep_changed(self, index: int):
        if index < 0:
            return
        self._save_ui_state()
        self._load_doctors()

    def on_date_changed(self, date: QDate):
        self._save_ui_state()
        self._load_doctors()

    def _load_doctors(self):
        unit_id = self.hospital_combo.currentData()
        dep_id = self.dep_combo.currentData()
        if unit_id in (None, "") or dep_id in (None, ""):
            return
        if not self.login_checked:
            if not self.pending_doctor_query:
                self.log("登录状态验证中，稍后自动查询排班", "#FF9500")
            self.pending_doctor_query = True
            return
        if not self.is_logged_in:
            self.log("未登录，无法查询排班", "#FF3B30")
            return

        date_value = self.date_edit.date()
        min_date = self.date_edit.minimumDate()
        max_date = self.date_edit.maximumDate()
        if date_value < min_date:
            date_value = min_date
            self.date_edit.setDate(date_value)
            self.log("就诊日期超出范围，已自动调整到最早可选日期", "#FF9500")
        elif date_value > max_date:
            date_value = max_date
            self.date_edit.setDate(date_value)
            self.log("就诊日期超出范围，已自动调整到最晚可选日期", "#FF9500")
        date_str = date_value.toString("yyyy-MM-dd")

        self.log(f"正在查询 {date_str} 的排班...")
        self.doctor_combo.clear()
        self.doctor_combo.addItem("查询中...", "")

        def load():
            try:
                docs = self.client.get_schedule(unit_id, dep_id, date_str)
                self.signals.doctors_loaded.emit(docs)
                if docs:
                    self.signals.log.emit(f"发现 {len(docs)} 位医生有排班", "#00D26A")
                else:
                    err = getattr(self.client, "last_error", None)
                    if err:
                        self.signals.log.emit(err, "#FF3B30")
                        if "登录" in err or "access_hash" in err:
                            self.signals.login_status.emit(False)
                    else:
                        self.signals.log.emit("该日期无号源", "#FF9500")
            except Exception as e:
                self.signals.log.emit(f"查询排班失败: {e}", "#FF3B30")

        threading.Thread(target=load, daemon=True).start()

    def _update_doctors(self, docs: list):
        items: List[tuple] = []
        for d in docs or []:
            left = d.get("total_left_num", "?")
            fee = d.get("reg_fee", "?")
            name = d.get("doctor_name", "")
            doc_id = d.get("doctor_id")
            # 格式: (Text, ID, LeftNum, Fee)
            items.append((name, doc_id, left, fee))
            
        self.doctor_combo.fast_add_items(
            items,
            static_items=[("全部医生 (智能筛选)", "")]
        )

        if self.saved_state.get("doctor_id"):
            self._try_restore_selection(self.doctor_combo, self.saved_state["doctor_id"])

    def _update_members(self, members: list):
        items = [(m.get("name", ""), m.get("id", "")) for m in members or []]
        self.member_combo.fast_add_items(items)

        if self.saved_state.get("member_id"):
            self._try_restore_selection(self.member_combo, self.saved_state["member_id"])

    def _update_login_status(self, logged_in: bool):
        self.is_logged_in = logged_in
        self.login_checked = True
        if logged_in:
            self.status_badge.setText("已登录")
            self.status_badge.setProperty("status", "success")
        else:
            self.status_badge.setText("未登录")
            self.status_badge.setProperty("status", "warning")
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)
        if logged_in and self.pending_hospital_load:
            self.pending_hospital_load = False
            self.pending_dep_load = False
            self.on_city_changed(self.city_combo.currentIndex())
        elif logged_in and self.pending_dep_load:
            self.pending_dep_load = False
            self.on_hospital_changed(self.hospital_combo.currentIndex())
        if logged_in and self.pending_doctor_query:
            self.pending_doctor_query = False
            self._load_doctors()

    def on_login_click(self):
        self.qr_dialog = QRLoginDialog(self)
        self.qr_dialog.show()
        self.start_qr_login()

    def start_qr_login(self):
        self.log("正在启动浏览器，请稍候...")

        def run_login():
            from core.qr_login import FastQRLogin, QRLoginResult

            stop_flag = [False]

            if self.qr_dialog:
                self.qr_dialog.stop_flag = stop_flag

            def on_qr(qr_bytes: bytes):
                self.signals.log.emit(f"收到二维码 ({len(qr_bytes)} bytes)", "#00D26A")
                self.signals.qr_image.emit(qr_bytes)

            def on_status(msg: str):
                self.signals.log.emit(f"登录状态: {msg}", "#AAAAAA")
                self.signals.qr_status.emit(msg)

            try:
                login = FastQRLogin()

                try:
                    on_status("正在获取二维码...")
                    qr_bytes, uuid = login.get_qr_image()
                    on_qr(qr_bytes)
                    on_status("请使用微信扫码")
                except Exception as e:
                    self.signals.qr_status.emit(f"获取二维码失败: {e}")
                    self.signals.log.emit(f"获取二维码失败: {e}", "#FF3B30")
                    self.signals.grab_finished.emit(False, str(e))
                    return

                try:
                    result = login.poll_status(
                        timeout_sec=300,
                        on_status=on_status,
                        stop_flag=stop_flag,
                    )
                except Exception as e:
                    result = QRLoginResult(False, f"轮询异常: {e}")

                if result.success:
                    self.signals.log.emit(f"登录成功! Cookie已保存: {result.cookie_path}", "#00D26A")
                    self.signals.login_status.emit(True)

                    try:
                        self.client.load_cookies()
                        members = self.client.get_members()
                        self.signals.members_loaded.emit(members)
                    except Exception as e:
                        self.signals.log.emit(f"加载就诊人失败: {e}", "#FF9500")

                    self.signals.qr_close.emit()

                    self.signals.grab_finished.emit(True, "登录成功")
                else:
                    msg = result.message or "未知错误"
                    if msg != "已取消":
                        self.signals.log.emit(f"登录失败: {msg}", "#FF3B30")
                    self.signals.grab_finished.emit(False, msg)

            except Exception as e:
                self.signals.log.emit(f"登录过程发生错误: {e}", "#FF3B30")
                import traceback
                traceback.print_exc()
                self.signals.grab_finished.emit(False, str(e))

        threading.Thread(target=run_login, daemon=True).start()

    def _show_qr_image(self, image_bytes: bytes):
        if self.qr_dialog:
            self.qr_dialog.set_qr_image(image_bytes)

    def _update_qr_status(self, text: str):
        if self.qr_dialog:
            self.qr_dialog.set_status(text)

    def _close_qr_dialog(self):
        if self.qr_dialog:
            self.qr_dialog.accept()

    def _update_start_button(self, text: str, object_name: str):
        self.start_btn.setText(text)
        self.start_btn.setObjectName(object_name)
        self.start_btn.style().unpolish(self.start_btn)
        self.start_btn.style().polish(self.start_btn)

    def toggle_grab(self):
        if self.is_running:
            self.is_running = False
            self.grab_stop_event.set()
            self.signals.update_button.emit("🚀 开始抢号", "primary")
            self.log("任务已手动停止", "#FF9500")
        else:
            if not self.hospital_combo.currentData():
                self.log("⚠️ 请先选择医院！", "#FF3B30")
                return
            if not self.dep_combo.currentData():
                self.log("⚠️ 请先选择科室！", "#FF3B30")
                return
            if not self.member_combo.currentData():
                self.log("⚠️ 请先选择就诊人！", "#FF3B30")
                return

            self.is_running = True
            self.grab_stop_event.clear()
            self.signals.update_button.emit("⏹️ 停止抢号", "danger")

            self.log(">>> 启动高频抢号引擎 <<<", "#00D26A")
            self.log(f"目标日期: {self.date_edit.date().toString('yyyy-MM-dd')}")

            self.grab_thread = threading.Thread(target=self._grab_loop, daemon=True)
            self.grab_thread.start()

    def _grab_loop(self):
        from core.grab import grab
        import time

        grab_client = HealthClient()
        grab_client.load_cookies()
        has_access_hash = any(
            c.name == "access_hash" and c.value
            for c in grab_client.session.cookies
        )
        if not has_access_hash:
            self.signals.log.emit("缺少 access_hash，请重新扫码登录", "#FF3B30")
            self.signals.login_status.emit(False)
            self.is_running = False
            self.signals.update_button.emit("🚀 开始抢号", "primary")
            return

        config = self._build_grab_config()
        retry_interval = 0.5
        attempt = 0

        while self.is_running and not self.grab_stop_event.is_set():
            attempt += 1
            self.signals.log.emit(f"第 {attempt} 次尝试...", "#FFFFFF")

            success = grab(
                config,
                grab_client,
                on_log=self._emit_grab_log,
                stop_event=self.grab_stop_event,
            )

            if success:
                self.signals.log.emit("抢号成功，任务结束", "#00D26A")
                break

            last_error = getattr(grab_client, "last_error", "") or ""
            if "登录" in last_error or "access_hash" in last_error:
                self.signals.log.emit(last_error, "#FF3B30")
                self.signals.login_status.emit(False)
                break

            if not self.is_running or self.grab_stop_event.is_set():
                break

            time.sleep(retry_interval)

        self.is_running = False
        self.signals.update_button.emit("🚀 开始抢号", "primary")
        if self.grab_stop_event.is_set():
            self.signals.log.emit("抢号任务已停止", "#FF9500")
        else:
            self.signals.log.emit("抢号任务已结束", "#FF9500")
