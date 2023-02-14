#!/usr/bin/python
# dave@fio.ie

import logging
import threading
from gi.repository import Nautilus, Gio, GObject, GLib
import urllib.parse
import os
import gi

from MediaInfoExtHelpers import file_info_update, run_task
from MediaInfoFileBot import *
import hashlib

gi.require_version("Nautilus", "4.0")
gi.require_version("Gtk", "4.0")


GObject.threads_init()

logging.basicConfig(filename="/tmp/VideoMetadataExtension.log", level=logging.DEBUG)


def nautilus_module_initialize(module):
    type_list = [
        Nautilus.InfoProvider,
        Nautilus.MenuProvider,
        Nautilus.ColumnProvider,
        Nautilus.PropertiesModelProvider,
    ]
    provider = GObject.type_register(VideoMetadataExtension)
    Nautilus.module_register_type(module, provider, type_list)


class VideoMetadataExtension(
    GObject.GObject,
    Nautilus.InfoProvider,
    Nautilus.MenuProvider,
    Nautilus.ColumnProvider,
    Nautilus.PropertiesModelProvider,
):
    def __init__(self):

        self.details = {}
        self.threads = {}
        self.lock = threading.Lock()
        self.queue = []

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

        super().__init__()
        self.timers = []

    ###########################################################################
    # Nautilus.PropertiesModelProvider
    ###########################################################################

    def get_models(self, files):
        if len(files) != 1:
            return []

        file = files[0]
        if file.get_uri_scheme() != "file":
            return []

        if file.is_directory():
            return []

        filename = urllib.parse.unquote(file.get_uri()[7:]).encode("utf-8")

        section_model = Gio.ListStore.new(item_type=Nautilus.PropertiesItem)

        section_model.append(
            Nautilus.PropertiesItem(
                name="MD5 sum of the filename",
                value=hashlib.md5(filename).hexdigest(),
            )
        )

        return [
            Nautilus.PropertiesModel(
                title="MD5Sum",
                model=section_model,
            ),
        ]

    ###########################################################################
    # Nautilus.ColumnProvider
    ###########################################################################

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

    ###########################################################################
    # Nautilus.InfoProvider
    ###########################################################################

    def update_file_info(self, file):
        logging.debug("update_file_info")

    def update_file_info_full(self, provider, handle, closure, file_info):
        logging.debug("update_file_info_full")

        filename = urllib.parse.unquote(file_info.get_uri()[7:])

        if filename in self.details.keys():
            self.details[filename]["file_info"] = file_info
            file_info_update(self, filename)
            return Nautilus.OperationResult.COMPLETE

        if file_info.get_uri_scheme() != "file":
            # logging.debug("Skipped wrong uri scheme: " +
            #               file_info.get_uri_scheme())
            return Nautilus.OperationResult.COMPLETE

        if os.path.isfile(filename) is False:
            # logging.debug("Skipped not a file: " + filename)
            return Nautilus.OperationResult.COMPLETE

        is_mime = False
        for mime in self.videomimes:
            if file_info.is_mime_type(mime):
                is_mime = True
                break

        if is_mime is False:
            # logging.debug("Skipped wrong mime: " + filename)
            return Nautilus.OperationResult.COMPLETE

        self.timers.append(
            GLib.timeout_add_seconds(
                1, self.update_info, provider, handle, closure, file_info
            )
        )
        return Nautilus.OperationResult.IN_PROGRESS

    def update_info(self, provider, handle, closure, file_info):
        logging.debug("update_info")
        filename = urllib.parse.unquote(file_info.get_uri()[7:])

        logging.debug("Looking for update on:" + filename)

        with self.lock:

            if filename in self.details.keys():
                logging.debug("Completed :" + filename)
                file_info_update(self, filename)
                Nautilus.info_provider_update_complete_invoke(
                    closure,
                    provider,
                    handle,
                    Nautilus.OperationResult.COMPLETE,
                )
                del self.threads[filename]
                return False

            if filename not in self.threads.keys():
                logging.debug("Starting thread :" + filename)
                thread = threading.Thread(
                    target=run_task,
                    args=(self, file_info),
                )
                self.threads[filename] = thread
                thread.start()

        return True

    def cancel_update(self, provider, handle):
        logging.debug("cancel_update")
        for t in self.timers:
            GObject.source_remove(t)
        self.timers = []

    ###########################################################################
    # Nautilus.MenuProvider
    ###########################################################################

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

    def get_file_items(self, files):
        logging.debug("get_file_items")

    def get_background_items(self, folder):
        logging.debug("get_background_items")

    def get_background_items_full(self, provider, folder):
        logging.debug("get_background_items_full")

    ###########################################################################
    ###########################################################################

    def filebot_activate_cb(self, menu, files, source):
        self.win = FileBotWindow(self, source, files)
        self.win.connect("delete-event", Gtk.main_quit)
        self.win.show_all()
        Gtk.main()
