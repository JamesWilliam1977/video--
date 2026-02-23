"""
 @file
 @brief This file is used to find missing files when opening or importing a project
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
from classes import info
from classes.app import get_app
from PyQt5.QtWidgets import QMessageBox, QFileDialog

# Keep track of all previously checked paths, and keep checking them
known_paths = [info.HOME_PATH]


def find_missing_file(file_path, prompt_state=None):
    """Find a missing file name or file path, and return valid path."""
    _ = get_app()._tr
    modified = False
    skipped = False
    if prompt_state is not None:
        prompt_state["last_skip"] = None

    # If user cancelled prompts, skip searching
    if prompt_state and prompt_state.get("cancelled"):
        if prompt_state is not None:
            prompt_state["last_skip"] = "all"
        return ("", modified, True)

    # Bail if path is already valid
    if os.path.exists(file_path):
        return (file_path, modified, skipped)

    # Original filename
    file_name = os.path.split(file_path)[-1]

    # Loop through all known paths, and check for this file
    for known_path in known_paths:
        possible_path = os.path.join(known_path, file_name)
        if os.path.exists(possible_path):
            modified = True
            return (possible_path, modified, skipped)

    # Check if path exists
    while not os.path.exists(file_path):
        recommended_path = get_app().project.current_filepath or ""
        if not recommended_path:
            recommended_path = info.HOME_PATH
        else:
            recommended_path = os.path.dirname(recommended_path)
        message_box = QMessageBox()
        message_box.setIcon(QMessageBox.Warning)
        message_box.setWindowTitle(_("Missing File (%s)") % file_name)
        message_box.setText(_("%s cannot be found.") % file_name)
        browse_button = message_box.addButton(_("Browse..."), QMessageBox.AcceptRole)
        skip_file_button = message_box.addButton(_("Skip File"), QMessageBox.DestructiveRole)
        skip_all_button = message_box.addButton(_("Skip All"), QMessageBox.RejectRole)
        message_box.setDefaultButton(browse_button)
        message_box.exec_()
        modified = True

        if message_box.clickedButton() == skip_all_button:
            # User skipped all missing file prompts
            skipped = True
            if prompt_state is not None:
                prompt_state["cancelled"] = True
                prompt_state["last_skip"] = "all"
            return ("", modified, skipped)

        if message_box.clickedButton() == skip_file_button:
            # User skipped this missing file only
            skipped = True
            if prompt_state is not None:
                prompt_state["last_skip"] = "file"
            return ("", modified, skipped)

        folder_to_check = QFileDialog.getExistingDirectory(None, _("Find directory that contains: %s" % file_name),
                                                           recommended_path)
        if folder_to_check and folder_to_check not in known_paths:
            known_paths.append(folder_to_check)
        if folder_to_check == "":
            # User hit cancel on folder dialog - treat as skip this file.
            skipped = True
            if prompt_state is not None:
                prompt_state["last_skip"] = "file"
            return ("", modified, skipped)
        file_path = os.path.join(folder_to_check, file_name)

    # Return found file_path
    return (file_path, modified, skipped)
