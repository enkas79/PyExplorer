"""
Foglio di stile centralizzato (QSS) per PyExplorer.
"""

STYLE_SHEET = """
            QMainWindow { background-color: #f5f6fa; }
            QFrame#Sidebar { background-color: #1f2a38; border-right: 1px solid #10151c; }
            QListWidget#ProfileList { background: transparent; border: none; color: #ecf0f1; font-size: 13px; outline: none; }
            QListWidget#ProfileList::item { padding: 8px 12px; border-radius: 6px; margin: 2px 8px; }
            QListWidget#ProfileList::item:hover { background-color: #2c3e50; }
            QListWidget#ProfileList::item:selected { background-color: #2980b9; color: white; }
            QLabel#Title { color: #ecf0f1; font-weight: 600; padding: 14px 12px 8px 12px; font-size: 12px; letter-spacing: 1px; }
            QFrame#ConnPanel { background: white; border: 1px solid #e1e4e8; border-radius: 8px; }
            QLineEdit { padding: 7px 10px; border: 1px solid #d0d5dd; border-radius: 6px; background: white; }
            QLineEdit:focus { border: 1px solid #2980b9; }
            QPushButton { padding: 7px 14px; border-radius: 6px; border: none; background-color: #dfe4ea; }
            QPushButton:hover { background-color: #ced6e0; }
            QPushButton:disabled { background-color: #eceff3; color: #a8b0bb; }
            QPushButton#Primary { background-color: #27ae60; color: white; font-weight: 600; }
            QPushButton#Primary:hover { background-color: #219150; }
            QPushButton#Secondary { background-color: #2980b9; color: white; }
            QPushButton#Secondary:hover { background-color: #2574a9; }
            QPushButton#Danger { background-color: #c0392b; color: white; }
            QPushButton#Danger:hover { background-color: #a93226; }
            QListWidget { background: white; border: 1px solid #e1e4e8; border-radius: 6px; padding: 4px; outline: none; }
            QListWidget::item { padding: 6px 8px; border-radius: 4px; }
            QListWidget::item:hover { background-color: #eef2f7; }
            QListWidget::item:selected { background-color: #d6e9f8; color: #1a1a1a; }
            QToolButton { border: none; padding: 5px; border-radius: 5px; }
            QToolButton:hover { background-color: #e1e8ee; }
            QToolButton:disabled { color: #c2c9d1; }
            QScrollArea#BreadcrumbArea { border: none; background: white; }
"""
