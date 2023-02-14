#!/usr/bin/python
# dave@fio.ie


from subprocess import Popen, PIPE
import os
import urllib.parse
import threading
from gi.repository import GObject, Gtk, Gdk
import gi

gi.require_version("Nautilus", "4.0")
gi.require_version("Gtk", "4.0")


GObject.threads_init()


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
        output, err = p.communicate(
            b"input data that is passed to subprocess' stdin")
        rc = p.returncode

        if self.processing == self.todo:
            GObject.idle_add(self.close, priority=GObject.PRIORITY_DEFAULT)
