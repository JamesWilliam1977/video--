"""
 @file
 @brief This file contains the emoji model, used by the main window
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2018 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

import os

from qt_api import QMimeData, Qt, QSortFilterProxyModel, Signal, QRegularExpression, QMessageBox
from qt_api import QStandardItemModel, QStandardItem, QIcon
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info
from classes.logger import log
from classes.app import get_app

import json


class EmojiStandardItemModel(QStandardItemModel):
    def __init__(self, parent=None):
        QStandardItemModel.__init__(self)

    def mimeData(self, indexes):
        # Create MimeData for drag operation
        data = QMimeData()

        # Get list of all selected file ids
        files = []
        for item in indexes:

            selected_item = self.itemFromIndex(item)
            files.append(selected_item.data())
        data.setText(json.dumps(files))
        data.setHtml("clip")

        # Return Mimedata
        return data


class EmojisModel(QSortFilterProxyModel):
    ModelRefreshed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = EmojiStandardItemModel()
        self.model.setColumnCount(3)
        self.setSourceModel(self.model)
        self.emoji_groups = []
        self.model_paths = {}
        # Configure proxy filtering/sorting
        self.setDynamicSortFilter(True)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setSortCaseSensitivity(Qt.CaseSensitive)
        self.setSortLocaleAware(True)
        self.setFilterKeyColumn(0)
        self.group_filter = ""
        self.text_regex = QRegularExpression()

    def set_group_filter(self, group_id: str):
        self.group_filter = group_id or ""
        self.invalidateFilter()

    def set_text_filter(self, pattern: str):
        self.text_regex = QRegularExpression(pattern, QRegularExpression.CaseInsensitiveOption)
        self.setFilterRegularExpression(self.text_regex)

    def update_model(self, clear=True):
        log.info("updating emoji model.")
        app = get_app()

        _ = app._tr

        # Clear all items
        if clear:
            self.model_paths = {}
            self.model.clear()
            self.emoji_groups.clear()

        # Add Headers
        self.model.setHorizontalHeaderLabels([_("Name")])

        # Get emoji metadata
        emoji_metadata_path = os.path.join(info.PATH, "emojis", "data", "openmoji-optimized.json")
        with open(emoji_metadata_path, 'r', encoding="utf-8") as f:
            emoji_lookup = json.load(f)

        # get a list of files in the OpenShot /emojis directory
        emojis_dir = os.path.join(info.PATH, "emojis", "color", "svg")
        emoji_paths = [{"type": "common", "dir": emojis_dir, "files": os.listdir(emojis_dir)}, ]

        # Add optional user-defined transitions folder
        if os.path.exists(info.EMOJIS_PATH) and os.listdir(info.EMOJIS_PATH):
            emoji_paths.append({"type": "user", "dir": info.EMOJIS_PATH, "files": os.listdir(info.EMOJIS_PATH)})

        for group in emoji_paths:
            dir = group["dir"]
            files = group["files"]

            for filename in sorted(files):
                path = os.path.join(dir, filename)
                fileBaseName = os.path.splitext(filename)[0]

                # Skip hidden files (such as .DS_Store, etc...)
                if filename[0] == "." or "thumbs.db" in filename.lower():
                    continue

                # get name of transition
                emoji = emoji_lookup.get(fileBaseName, {})
                emoji_name = _(emoji.get("annotation", fileBaseName).capitalize())
                emoji_group_name = _(emoji.get("group", "user").split('-')[0].capitalize())
                emoji_group_id = emoji.get("group", "user")
                emoji_group_tuple = (emoji_group_name, emoji_group_id)

                # Track unique emoji groups
                if emoji_group_tuple not in self.emoji_groups:
                    self.emoji_groups.append(emoji_group_tuple)

                # Check for thumbnail path (in build-in cache)
                thumb_path = os.path.join(info.IMAGES_PATH, "cache",  "{}.png".format(fileBaseName))

                # Check built-in cache (if not found)
                if not os.path.exists(thumb_path):
                    # Check user folder cache
                    thumb_path = os.path.join(info.CACHE_PATH, "{}.png".format(fileBaseName))

                # Generate thumbnail (if needed)
                if not os.path.exists(thumb_path):

                    try:
                        # Reload this reader
                        clip = openshot.Clip(path)
                        reader = clip.Reader()

                        # Open reader
                        reader.Open()

                        # Save thumbnail
                        reader.GetFrame(0).Thumbnail(
                            thumb_path, 75, 75,
                            os.path.join(info.IMAGES_PATH, "mask.png"),
                            "", "#000", True, "png", 85
                        )
                        reader.Close()
                        clip.Close()

                    except Exception:
                        # Handle exception
                        log.info('Invalid emoji image file: %s' % filename)
                        msg = QMessageBox()
                        msg.setText(_("{} is not a valid image file.".format(filename)))
                        msg.exec_()
                        continue

                row = []

                # Set emoji data
                col = QStandardItem("Name")
                col.setIcon(QIcon(thumb_path))
                col.setText(emoji_name)
                col.setToolTip(emoji_name)
                col.setData(path)
                col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
                row.append(col)

                # Append filterable group name
                col = QStandardItem(emoji_group_name)
                row.append(col)

                # Append filterable group id
                col = QStandardItem(emoji_group_id)
                row.append(col)

                # Append ROW to MODEL (if does not already exist in model)
                if path not in self.model_paths:
                    self.model.appendRow(row)
                    self.model_paths[path] = path

        self.ModelRefreshed.emit()

    def filterAcceptsRow(self, source_row, source_parent):
        if self.group_filter:
            group_idx = self.sourceModel().index(source_row, 2, source_parent)
            if self.sourceModel().data(group_idx) != self.group_filter:
                return False

        regex = self.filterRegularExpression()
        if regex.pattern():
            name_idx = self.sourceModel().index(source_row, 0, source_parent)
            value = self.sourceModel().data(name_idx)
            return regex.match(value).hasMatch()

        return True
