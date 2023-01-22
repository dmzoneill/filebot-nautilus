#!/usr/bin/python
# dave@fio.ie


import gi

gi.require_version("Nautilus", "4.0")
gi.require_version("Gtk", "4.0")

from gi.repository import Nautilus, GObject, Gtk, Gdk
from pprint import pprint
import json
import subprocess as sp
import threading
import re
import logging
import urllib.parse
import os
from subprocess import Popen, PIPE
import traceback

GObject.threads_init()


cache = {}
worker = None


class VideoMetadataExtension(
    GObject.GObject,
    Nautilus.ColumnProvider,
    Nautilus.MenuProvider,
    Nautilus.InfoProvider,
):
    def __init__(self):

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

        pprint(self.videomimes)

        self.win = None

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

    def update_file_info_full(self, provider, handle, closure, file_info):

        filename = urllib.parse.unquote(file_info.get_uri()[7:])

        if file_info.get_uri_scheme() != "file":
            pprint("Skipped: not file: " + filename)
            return Nautilus.OperationResult.COMPLETE

        for mime in self.videomimes:
            if file_info.is_mime_type(mime):
                GObject.timeout_add_seconds(
                    1, self.get_video_metadata, provider, handle, closure, file_info
                )
                pprint("in Progress: " + filename)
                return Nautilus.OperationResult.IN_PROGRESS

        pprint("Skipped file not in mimes: " + filename)
        pprint(file_info)

        return Nautilus.OperationResult.COMPLETE

    def get_file_items_full(self, provider, files):

        for mime in self.videomimes:
            for file in files:
                if file.get_uri_scheme() == "file" and file.is_mime_type(mime):

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
                        "activate", self.filebot_activate_cb, files, "tvdb"
                    )
                    submenu.append_item(filebot_tvdb_menuitem)

                    filebot_moviedb_menuitem = Nautilus.MenuItem(
                        name="NautilusPython::FilebotRenameMoviewDB",
                        label="Filebot MovieDB",
                        tip="Fetch names from MovieDB",
                    )
                    filebot_moviedb_menuitem.connect(
                        "activate", self.filebot_activate_cb, files, "moviedb"
                    )
                    submenu.append_item(filebot_moviedb_menuitem)

                    return (top_menuitem,)

    def filebot_activate_cb(self, menu, files, source):

        self.win = FileBotWindow(self, source, files)
        self.win.connect("delete-event", Gtk.main_quit)
        self.win.show_all()
        Gtk.main()

    def test_rename(self, file):
        pprint("filebot " + file)
        out = sp.run(
            ["filebot", "-rename", "-r", file, "-non-strict", "--action", "test"],
            stdout=sp.PIPE,
            stderr=sp.PIPE,
            universal_newlines=True,
        )

        p = re.compile("\[TEST\] from \[(.*?)\] to \[(.*?)\]")
        result = p.search(out.stdout)
        if result is not None:
            pprint(result.group(1))
            pprint(result.group(2))

        if result is not None:
            return [result.group(1), result.group(2)]
        else:
            pprint(out.stdout)
            return False

    def ffprobe(self, filename):
        pprint("ffprobe " + filename)
        out = sp.run(
            ["ffprobe", "-of", "json", "-show_entries", "format:stream", filename],
            stdout=sp.PIPE,
            stderr=sp.PIPE,
            universal_newlines=True,
        )
        return json.loads(out.stdout)

    def update_meta_data(self):
        pprint("Worker")
        keys = cache.keys()

        for X in list(keys):
            if "processed" in cache[X]:
                continue
            
            name_suggestion = self.test_rename(X)
            if name_suggestion is not False:
                parts = name_suggestion[1].split("/")
                name_suggestion = parts[len(parts) - 1]
            else:
                name_suggestion = ""

            cache[X]["name_suggestion"] = name_suggestion
            cache[X]["file_info"].add_string_attribute('name_suggestion', str(name_suggestion))

            results = self.ffprobe(X)

            cache[X]["video_width"] = (
                results["streams"][0]["coded_width"]
                if "coded_width" in results["streams"][0]
                else results["streams"][0]["width"]
            )
            cache[X]["file_info"].add_string_attribute('video_width', str(cache[X]["video_width"]))

            cache[X]["video_height"] = (
                results["streams"][0]["coded_height"]
                if "coded_height" in results["streams"][0]
                else results["streams"][0]["height"]
            )
            cache[X]["file_info"].add_string_attribute('video_height', str(cache[X]["video_height"]))

            cache[X]["video_codec_name"] = (
                results["streams"][0]["codec_name"]
                if "codec_name" in results["streams"][0]
                else ""
            )
            cache[X]["file_info"].add_string_attribute('video_codec_name', str(cache[X]["video_codec_name"]))

            cache[X]["audio_channels"] = (
                results["streams"][1]["channels"]
                if "channels" in results["streams"][1]
                else ""
            )
            cache[X]["file_info"].add_string_attribute('audio_channels', str(cache[X]["audio_channels"]))
            
            cache[X]["audio_codec_name"] = (
                results["streams"][1]["codec_name"]
                if "codec_name" in results["streams"][1]
                else ""
            )
            cache[X]["file_info"].add_string_attribute('audio_codec_name', str(cache[X]["audio_codec_name"]))

            cache[X]["processed"] = True

    def get_video_metadata(self, provider, handle, closure, file_info):

        filename = urllib.parse.unquote(file_info.get_uri()[7:])

        try:
            cache[filename] = {}
            cache[filename]["video_width"] = ""
            cache[filename]["video_height"] = ""
            cache[filename]["video_codec_name"] = ""
            cache[filename]["audio_codec_name"] = ""
            cache[filename]["audio_channels"] = ""
            cache[filename]["name_suggestion"] = ""
            cache[filename]["file_info"] = file_info
            cache[filename]["closure"] = closure
            cache[filename]["provider"] = provider
            cache[filename]["handle"] = handle

            self.update_meta_data()

            Nautilus.info_provider_update_complete_invoke(closure, provider, 
                               handle, Nautilus.OperationResult.COMPLETE)
            return False
        except Exception as e:
            pprint("Unable to extract metadata: " + filename)
            pprint(e)
            traceback.print_exc()
            Nautilus.info_provider_update_complete_invoke(
                closure, provider, handle, Nautilus.OperationResult.FAILED
            )
            return False


class FileBotWindow(Gtk.Window):
    def __init__(self, videoMetadataExtension, source, files):

        self.todo = len(files)
        self.processing = 0
        self.files = files
        self.source = source
        self.quit = False

        self.videoMetadataExtension = videoMetadataExtension

        Gtk.Window.__init__(self, title="Filebot operation")
        self.set_size_request(200, 100)
        self.set_border_width(10)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(vbox)

        self.working_label = Gtk.Label(label="Working")
        vbox.pack_start(self.working_label, True, True, 0)

        self.button = Gtk.Button(label="Cancel")
        self.button.connect("clicked", self.on_button_clicked)
        vbox.pack_start(self.button, True, True, 0)

        # GObject.timeout_add_seconds(1, self.process, files, source)
        self.update = threading.Thread(target=self.process)
        self.update.setDaemon(True)
        self.update.start()

    def process(self):

        for file in self.files:
            if file.get_uri_scheme() != "file":
                continue

            filename = urllib.unquote(file.get_uri()[7:])
            self.filebot_process(filename)

    def on_button_clicked(self, widget):
        self.quit = True
        self.close()

    def filebot_process(self, filename):

        if self.quit == True:
            return

        self.processing = self.processing + 1
        text = (
            "Processing ("
            + str(self.processing)
            + "/"
            + str(self.todo)
            + ") "
            + os.path.basename(filename)
        )
        GObject.idle_add(
            self.working_label.set_text, text, priority=GObject.PRIORITY_DEFAULT
        )

        p = Popen(
            ["filebot", "-rename", filename, "--db", self.source],
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
        )
        output, err = p.communicate(b"input data that is passed to subprocess' stdin")
        rc = p.returncode

        if self.processing == self.todo:
            GObject.idle_add(self.close, priority=GObject.PRIORITY_DEFAULT)
