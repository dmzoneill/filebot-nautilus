#!/usr/bin/python
# dave@fio.ie

import logging
import threading
from gi.repository import Nautilus, GObject
import urllib.parse
import os
import gi

from MediaInfoExtHelpers import run_task
from MediaInfoFileBot import *

gi.require_version("Nautilus", "4.0")
gi.require_version("Gtk", "4.0")


GObject.threads_init()


def nautilus_module_initialize(module):
    type_list = [Nautilus.InfoProvider, Nautilus.MenuProvider, Nautilus.ColumnProvider]
    provider = GObject.type_register(VideoMetadataExtension)
    Nautilus.module_register_type(module, provider, type_list)


class VideoMetadataExtension(
    GObject.GObject,
    Nautilus.InfoProvider,
    Nautilus.MenuProvider,
    Nautilus.ColumnProvider,
):
    def __init__(self):

        self.details = {}
        self.lock = threading.Lock()

        logging.basicConfig(
            filename="/tmp/VideoMetadataExtension.log", level=logging.DEBUG
        )

        self.videomimes = [
            "video/x-msvideo",
            "video/mpeg",
            "video/x-ms-wmv",
            "video/mp4",
            "video/x-flv",
            "video/x-matroska",
        ]

    def get_columns(self):

        return (
            Nautilus.Column(
                name="NautilusPython::video_width_columnn",
                attribute="video_width",
                label="Width",
                description="Video width",
            ),
            Nautilus.Column(
                name="NautilusPython::video_height_columnn",
                attribute="video_height",
                label="Height",
                description="Video height",
            ),
            Nautilus.Column(
                name="NautilusPython::video_codec_name_columnn",
                attribute="video_codec_name",
                label="Video Codec",
                description="Video codec name",
            ),
            Nautilus.Column(
                name="NautilusPython::audio_codec_name_columnn",
                attribute="audio_codec_name",
                label="Audio Codec",
                description="Audio codec name",
            ),
            Nautilus.Column(
                name="NautilusPython::audio_channels_columnn",
                attribute="audio_channels",
                label="Audio channels",
                description="Audio channels",
            ),
            Nautilus.Column(
                name="NautilusPython::name_suggestion_columnn",
                attribute="name_suggestion",
                label="Filebot suggested name",
                description="name suggestion",
            ),
        )

    # Fixed code
    def cancel_update(self, provider, handle):
        pass

    def update_file_info_full(self, provider, handle, closure, file_info):
        filename = urllib.parse.unquote(file_info.get_uri()[7:])

        if file_info.get_uri_scheme() != "file":
            # print("Skipped wrong uri scheme: " + file_info.get_uri_scheme())
            return Nautilus.OperationResult.COMPLETE

        if os.path.isfile(filename) is False:
            # print("Skipped not a file: " + filename)
            return Nautilus.OperationResult.COMPLETE

        is_mime = False
        for mime in self.videomimes:
            if file_info.is_mime_type(mime):
                is_mime = True
                break

        if is_mime is False:
            # print("Skipped wrong mime: " + filename)
            return Nautilus.OperationResult.COMPLETE

        self.details[filename] = {}
        self.details[filename]["file_info"] = file_info

        thread = threading.Thread(
            target=run_task,
            args=(self, provider, handle, closure, self.details[filename]["file_info"]),
        )
        thread.start()

        # return Nautilus.OperationResult.COMPLETE
        return

    def get_file_items_full(self, provider, files):
        if len(files) != 1:
            return

        file = files[0]
        if file.is_directory() or file.get_uri_scheme() != "file":
            return

        top_menuitem = Nautilus.MenuItem(
            name="NautilusPython::Filebot",
            label="Filebot",
            tip="Filebot renamer",
        )

        submenu = Nautilus.Menu()
        top_menuitem.set_submenu(submenu)

        filebot_tvdb_menuitem = Nautilus.MenuItem(
            name="NautilusPython::FilebotRenameTVDB",
            label="Filebot TVDB",
            tip="Fetch names from TVDB",
        )
        filebot_tvdb_menuitem.connect(
            "activate", self.filebot_activate_cb, file, "tvdb"
        )
        submenu.append_item(filebot_tvdb_menuitem)

        filebot_moviedb_menuitem = Nautilus.MenuItem(
            name="NautilusPython::FilebotRenameMoviewDB",
            label="Filebot MovieDB",
            tip="Fetch names from MovieDB",
        )
        filebot_moviedb_menuitem.connect(
            "activate", self.filebot_activate_cb, file, "moviedb"
        )
        submenu.append_item(filebot_moviedb_menuitem)

        return (top_menuitem,)

    def filebot_activate_cb(self, menu, files, source):
        self.win = FileBotWindow(self, source, files)
        self.win.connect("delete-event", Gtk.main_quit)
        self.win.show_all()
        Gtk.main()

    def get_file_items(self, files):
        return

    def get_background_items(self, folder):
        return

    def get_background_items_full(self, provider, folder):
        return
