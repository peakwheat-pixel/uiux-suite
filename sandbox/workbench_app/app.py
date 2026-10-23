"""Synthetic PySide6 workbench used for Stage 5 end-to-end validation.

It is *not* a product UI; it is a deterministic test application with import,
list browse, canvas edit, save, export, undo and error handling.  All data is
synthetic and lives in a temp/isolated directory.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QAction, QColor, QPainter, QPen, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QFileDialog,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


@dataclass
class Item:
    item_id: str
    name: str
    x: float
    y: float


@dataclass
class Document:
    items: list[Item] = field(default_factory=list)
    path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"items": [item.__dict__ for item in self.items]}


class AddItemCommand(QUndoCommand):
    def __init__(self, window: "MainWindow", item: Item) -> None:
        super().__init__("add item")
        self.window = window
        self.item = item

    def redo(self) -> None:
        self.window.document.items.append(self.item)
        self.window.refresh()

    def undo(self) -> None:
        self.window.document.items.remove(self.item)
        self.window.refresh()


class DeleteItemCommand(QUndoCommand):
    def __init__(self, window: "MainWindow", item: Item) -> None:
        super().__init__("delete item")
        self.window = window
        self.item = item
        self.index = window.document.items.index(item)

    def redo(self) -> None:
        self.window.document.items.pop(self.index)
        self.window.refresh()

    def undo(self) -> None:
        self.window.document.items.insert(self.index, self.item)
        self.window.refresh()


class MoveItemCommand(QUndoCommand):
    def __init__(self, window: "MainWindow", item: Item, old: tuple[float, float], new: tuple[float, float]) -> None:
        super().__init__("move item")
        self.window = window
        self.item = item
        self.old = old
        self.new = new

    def redo(self) -> None:
        self.item.x, self.item.y = self.new
        self.window.refresh()

    def undo(self) -> None:
        self.item.x, self.item.y = self.old
        self.window.refresh()


class CanvasView(QGraphicsView):
    """Canvas with a real mouse drag that records an undoable move."""

    def __init__(self, window: "MainWindow") -> None:
        super().__init__()
        self.window = window
        self._drag_item = None
        self._start = None
        self._origin = None
        self._moved = False

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        item = self.itemAt(event.position().toPoint())
        if item is not None:
            self._drag_item = item
            self._start = event.position()
            self._origin = item.pos()
            self._moved = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._drag_item is not None and self._start is not None:
            delta = event.position() - self._start
            self._drag_item.setPos(self._origin + delta)
            self._moved = True
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._drag_item is not None and self._moved:
            index = self.window.scene_items.index(self._drag_item)
            item = self.window.document.items[index]
            old = (item.x, item.y)
            new = (self._drag_item.pos().x(), self._drag_item.pos().y())
            self.window.undo_stack.push(MoveItemCommand(self.window, item, old, new))
        self._drag_item = None
        self._start = None
        self._origin = None
        self._moved = False
        super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, theme: str = "after") -> None:
        super().__init__()
        self.theme = theme
        self.document = Document()
        self.undo_stack = QUndoStack(self)
        self.setWindowTitle(f"Workbench ({theme})")
        self.resize(900, 600)
        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        toolbar = QHBoxLayout()
        self.import_button = QPushButton("Import")
        self.import_button.setObjectName("importButton")
        self.import_button.clicked.connect(self.import_via_dialog)
        self.add_button = QPushButton("Add")
        self.add_button.setObjectName("addButton")
        self.add_button.clicked.connect(self.add_item)
        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("deleteButton")
        self.delete_button.clicked.connect(self.delete_item)
        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("saveButton")
        self.save_button.clicked.connect(self.save_document)
        self.export_button = QPushButton("Export")
        self.export_button.setObjectName("exportButton")
        self.export_button.clicked.connect(self.export_document)
        for button in (self.import_button, self.add_button, self.delete_button, self.save_button, self.export_button):
            toolbar.addWidget(button)
        layout.addLayout(toolbar)

        body = QHBoxLayout()
        self.table = QTableWidget(0, 3)
        self.table.setObjectName("itemTable")
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Position"])
        self.table.itemSelectionChanged.connect(self._selection_changed)
        body.addWidget(self.table, 2)

        self.canvas = CanvasView(self)
        self.canvas.setObjectName("canvasView")
        self.scene = QGraphicsScene(self)
        self.canvas.setScene(self.scene)
        self.scene_items: list = []
        body.addWidget(self.canvas, 3)
        layout.addLayout(body)

        editor = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("nameEdit")
        self.x_spin = QDoubleSpinBox()
        self.x_spin.setObjectName("xSpin")
        self.x_spin.setRange(-5000, 5000)
        self.y_spin = QDoubleSpinBox()
        self.y_spin.setObjectName("ySpin")
        self.y_spin.setRange(-5000, 5000)
        self.apply_button = QPushButton("Apply")
        self.apply_button.setObjectName("applyButton")
        self.apply_button.clicked.connect(self.apply_edit)
        for widget in (QLabel("Name"), self.name_edit, QLabel("X"), self.x_spin, QLabel("Y"), self.y_spin, self.apply_button):
            editor.addWidget(widget)
        layout.addLayout(editor)
        self.setCentralWidget(central)

        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.triggered.connect(self.undo_stack.undo)
        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcut("Ctrl+Y")
        self.redo_action.triggered.connect(self.undo_stack.redo)
        self.addAction(self.undo_action)
        self.addAction(self.redo_action)

        menu = self.menuBar().addMenu("File")
        import_action = menu.addAction("Import")
        import_action.triggered.connect(self.import_via_dialog)
        save_action = menu.addAction("Save")
        save_action.triggered.connect(self.save_document)
        export_action = menu.addAction("Export")
        export_action.triggered.connect(self.export_document)

        self.status = self.statusBar()
        self.status.showMessage("ready")

    def _apply_style(self) -> None:
        if self.theme == "before":
            self.setStyleSheet(
                "QWidget { background: #fafafa; color: #b0b0b0; font-size: 11px; }"
                "QPushButton { min-width: 18px; min-height: 18px; padding: 1px; border: 1px solid #dddddd; }"
                "QLineEdit, QDoubleSpinBox { min-height: 18px; }"
            )
        else:
            self.setStyleSheet(
                "QWidget { background: #ffffff; color: #1f2328; font-size: 14px; }"
                "QPushButton { min-width: 64px; min-height: 28px; padding: 4px 10px; border: 1px solid #0969da; border-radius: 6px; }"
                "QLineEdit, QDoubleSpinBox { min-height: 28px; padding: 4px; }"
                "QTableWidget { gridline-color: #d0d7de; }"
            )

    # --- document operations -------------------------------------------------
    def import_path(self, path: str | Path) -> bool:
        path = Path(path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            items = [Item(str(item["item_id"]), str(item["name"]), float(item["x"]), float(item["y"])) for item in payload["items"]]
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Import failed", f"invalid document: {exc}")
            self.status.showMessage("import failed")
            return False
        self.document = Document(items=items, path=path)
        self.undo_stack.clear()
        self.refresh()
        self.status.showMessage(f"imported {len(items)} items")
        return True

    def import_via_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import", "", "JSON (*.json)")
        if path:
            self.import_path(path)

    def add_item(self) -> None:
        item = Item(f"item-{len(self.document.items) + 1}", f"Item {len(self.document.items) + 1}", 40.0, 40.0)
        self.undo_stack.push(AddItemCommand(self, item))
        self.status.showMessage("item added")

    def delete_item(self) -> None:
        item = self.current_item()
        if item is None:
            self.status.showMessage("nothing selected")
            return
        self.undo_stack.push(DeleteItemCommand(self, item))

    def apply_edit(self) -> None:
        item = self.current_item()
        if item is None:
            return
        old = (item.x, item.y)
        item.name = self.name_edit.text()
        item.x = float(self.x_spin.value())
        item.y = float(self.y_spin.value())
        self.undo_stack.push(MoveItemCommand(self, item, old, (item.x, item.y)))
        self.refresh()

    def save_document(self) -> bool:
        if self.document.path is None:
            self.document.path = Path("workbench-document.json")
        self.document.path.write_text(json.dumps(self.document.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        self.status.showMessage(f"saved {len(self.document.items)} items")
        return True

    def export_document(self) -> bool:
        target = (self.document.path or Path("workbench-document.json")).with_name("workbench-export.json")
        target.write_text(json.dumps(self.document.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        self.status.showMessage(f"exported {target.name}")
        return True

    def current_item(self) -> Item | None:
        row = self.table.currentRow()
        if 0 <= row < len(self.document.items):
            return self.document.items[row]
        return None

    def _selection_changed(self) -> None:
        item = self.current_item()
        if item is None:
            return
        self.name_edit.setText(item.name)
        self.x_spin.setValue(item.x)
        self.y_spin.setValue(item.y)

    def refresh(self) -> None:
        self.table.setRowCount(len(self.document.items))
        for row, item in enumerate(self.document.items):
            self.table.setItem(row, 0, QTableWidgetItem(item.item_id))
            self.table.setItem(row, 1, QTableWidgetItem(item.name))
            self.table.setItem(row, 2, QTableWidgetItem(f"{item.x:.0f},{item.y:.0f}"))
        self.scene.clear()
        self.scene_items = []
        for item in self.document.items:
            rect = self.scene.addRect(0, 0, 120, 60, QPen(QColor("#0969da")), QColor("#ddf4ff"))
            rect.setPos(item.x, item.y)
            self.scene_items.append(rect)
        self.scene.update()
        if self.document.items and self.table.currentRow() < 0:
            self.table.selectRow(0)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self.document.items:
            self.status.showMessage("closed")
        event.accept()


def create_app(argv: list[str] | None = None) -> tuple[QApplication, MainWindow, MainWindow]:
    app = QApplication.instance() or QApplication(argv or [])
    before = MainWindow("before")
    before.show()
    after = MainWindow("after")
    after.show()
    app.processEvents()
    return app, before, after


if __name__ == "__main__":
    app, before, after = create_app(sys.argv)
    raise SystemExit(app.exec())
