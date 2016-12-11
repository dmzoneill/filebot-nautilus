#!/usr/bin/python

# dave@fio.ie

import os
import urllib
import logging
import re
import threading

import gi
gi.require_version('Nautilus', '3.0')
gi.require_version('Gtk', '3.0')

from gi.repository import Nautilus, GObject, Gtk, Gdk, GLib, GdkPixbuf
from hachoir_core.error import HachoirError
from hachoir_core.stream import InputIOStream
from hachoir_parser import guessParser
from hachoir_metadata import extractMetadata
from subprocess import Popen, PIPE

GObject.threads_init()


class VideoMetadataExtension(GObject.GObject, Nautilus.ColumnProvider, Nautilus.MenuProvider, Nautilus.InfoProvider):

  def __init__(self):
  
    logging.basicConfig(filename='/tmp/VideoMetadataExtension.log',level=logging.DEBUG)
    
    self.videomimes = [
      'video/x-msvideo',
      'video/mpeg',
      'video/x-ms-wmv',
      'video/mp4',
      'video/x-flv',
      'video/x-matroska'
    ]
    
    self.win = None


  def get_columns(self):
  
    return (
      Nautilus.Column(name="NautilusPython::video_width_columnn",attribute="video_width",label="Width",description="Video width"),
      Nautilus.Column(name="NautilusPython::video_height_columnn",attribute="video_height",label="Height",description="Video height"),
    )


  def update_file_info_full(self, provider, handle, closure, file_info):
  
    filename = urllib.unquote(file_info.get_uri()[7:]) 
    video_width = ''
    video_height = ''
    name_suggestion = ''

    file_info.add_string_attribute('video_width', video_width)
    file_info.add_string_attribute('video_height', video_height)
    file_info.add_string_attribute('name_suggestion', name_suggestion)  
  
    if file_info.get_uri_scheme() != 'file':
      logging.debug("Skipped: " + filename)
      return Nautilus.OperationResult.COMPLETE
      
    for mime in self.videomimes:
      if file_info.is_mime_type(mime):
        GObject.idle_add(self.get_video_metadata, provider, handle, closure, file_info)
        logging.debug("in Progress: " + filename)
        return Nautilus.OperationResult.IN_PROGRESS
         
    logging.debug("Skipped: " + filename)
    
    return Nautilus.OperationResult.COMPLETE


  def get_file_items_full(self, provider, window, files):
  
    for mime in self.videomimes:
      for file in files:
        if file.get_uri_scheme() == 'file' and file.is_mime_type(mime):
      
          top_menuitem = Nautilus.MenuItem(name='NautilusPython::Filebot', label='Filebot', tip='Filebot renamer')

          submenu = Nautilus.Menu()
          top_menuitem.set_submenu(submenu)

          filebot_tvdb_menuitem = Nautilus.MenuItem(name='NautilusPython::FilebotRenameTVDB', label='Filebot TVDB', tip='Fetch names from TVDB')
          filebot_tvdb_menuitem.connect('activate', self.filebot_activate_cb, files, 'tvdb')
          submenu.append_item(filebot_tvdb_menuitem)

          filebot_moviedb_menuitem = Nautilus.MenuItem(name='NautilusPython::FilebotRenameMoviewDB', label='Filebot MovieDB', tip='Fetch names from MovieDB')
          filebot_moviedb_menuitem.connect('activate', self.filebot_activate_cb, files, 'moviedb')
          submenu.append_item(filebot_moviedb_menuitem)

          return top_menuitem,


  def filebot_activate_cb(self, menu, files, source):
  
    self.win = FileBotWindow(self, source, files)
    self.win.connect("delete-event", Gtk.main_quit)
    self.win.show_all()
    Gtk.main()
        

  def get_video_metadata(self, provider, handle, closure, file_info):
  
    video_width = ''
    video_height = ''
    name_suggestion = ''
  
    filename = urllib.unquote(file_info.get_uri()[7:])  
    filelike = open(filename, "rw+")
    
    try:
      filelike.seek(0)
    except (AttributeError, IOError):
      logging.debug("Unabled to read: " + filename)
      Nautilus.info_provider_update_complete_invoke(closure, provider, handle, Nautilus.OperationResult.FAILED)
      return False

    stream = InputIOStream(filelike, None, tags=[])
    parser = guessParser(stream)

    if not parser:
      logging.debug("Unabled to determine parser: " + filename)
      Nautilus.info_provider_update_complete_invoke(closure, provider, handle, Nautilus.OperationResult.FAILED)
      return False

    try:
      metadata = extractMetadata(parser)
    except HachoirError:
      logging.debug("Unabled to extract metadata: " + filename)
      Nautilus.info_provider_update_complete_invoke(closure, provider, handle, Nautilus.OperationResult.FAILED)
      return False
          
    if metadata is None:
      logging.debug("Metadata None: " + filename)
      Nautilus.info_provider_update_complete_invoke(closure, provider, handle, Nautilus.OperationResult.FAILED)
      return False

    matchObj = re.search( r'Image width: (.*?) pixels', str(metadata), re.M|re.I)

    if matchObj:
       video_width = matchObj.group(1)
        
    matchObj = re.search( r'Image height: (.*?) pixels', str(metadata), re.M|re.I)

    if matchObj:
       video_height = matchObj.group(1)

    file_info.add_string_attribute('video_width', video_width)
    file_info.add_string_attribute('video_height', video_height)
    file_info.add_string_attribute('name_suggestion', name_suggestion)   
    
    logging.debug("Completed: " + filename)
    
    file_info.invalidate_extension_info()
    
    Nautilus.info_provider_update_complete_invoke(closure, provider, handle, Nautilus.OperationResult.COMPLETE)
    
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
    
    #GObject.timeout_add_seconds(1, self.process, files, source)
    self.update = threading.Thread(target=self.process)
    self.update.setDaemon(True)
    self.update.start()
             
        
  def process(self):
 
    for file in self.files:
      if file.get_uri_scheme() != 'file':
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
    text = "Processing (" + str(self.processing) + "/" + str(self.todo) + ") " + os.path.basename(filename)
    GObject.idle_add( self.working_label.set_text, text, priority=GObject.PRIORITY_DEFAULT )
        
    p = Popen(['filebot', '-rename', filename,'--db', self.source], stdin=PIPE, stdout=PIPE, stderr=PIPE)
    output, err = p.communicate(b"input data that is passed to subprocess' stdin")
    rc = p.returncode

    if self.processing == self.todo:
      GObject.idle_add( self.close, priority=GObject.PRIORITY_DEFAULT )  
